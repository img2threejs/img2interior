#!/usr/bin/env python3
"""Audit declared material wiring and factors, never visual realism or texture pixels."""
import os, sys
sys.dont_write_bytecode = True
root = os.environ.get("IMG2_HOME")
if root: sys.path.insert(0, os.path.join(root, "harness"))
else:
    try: import _img2_local; sys.path.insert(0, _img2_local.CORE)
    except ImportError: sys.exit("img2: core not linked - run `img2 sync`")
from img2_core import require_core_api
require_core_api(1)

import base64
import binascii
import struct

from audit_support import (AuditFailure, JSON_LIMIT, Parser, check_pin, confined_file,
                           decode_json, emit, factor, fields, file_hash, input_path,
                           integer, load_receipt, object_value, persist, pin,
                           read_json, text, workspace_path)

GATE = "interior-materials"
RECEIPT = "material-audit.json"
STATE_KEY = "materialAudit"
LIMITATIONS = [
    "Only explicitly declared policy expectations are checked; omitted expectations are not certified.",
    "Texture pixels and image decoding are not evaluated. A scalar roughness factor is multiplied by the texture's green channel and does not prove effective roughness.",
    "Color-space interpretation, texel density, UV orientation, visible textile identity, lighting, and frontal/grazing appearance require separate consumer and visual review.",
    "This is a bounded material-wiring audit, not a Khronos validator, scene-visibility proof, native reopen, or runtime-render test.",
]


def array(doc, key):
    value = doc.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"glTF {key} must be an array")
    return value


def indexed(values, index, label):
    integer(index, label)
    if index >= len(values):
        raise ValueError(f"{label} index {index} out of range")
    return object_value(values[index], label)


def validate_policy(value):
    fields(value, ["schemaVersion", "materials"], [], "policy")
    if type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1:
        raise ValueError("policy schemaVersion must be 1")
    rows = value["materials"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("policy materials must be a nonempty array")
    names = set()
    booleans = {"requireBaseColorTexture", "requireNormalTexture", "requireRoughnessTexture"}
    numbers = {"minRoughnessFactor", "maxMetallicFactor", "maxSheenColorFactor"}
    for row in rows:
        fields(row, ["name"], booleans | numbers | {"texCoord"}, "material policy")
        name = text(row["name"], "material name")
        if name in names:
            raise ValueError(f"duplicate material policy target: {name}")
        names.add(name)
        for key in booleans & row.keys():
            if type(row[key]) is not bool:
                raise ValueError(f"{key} must be boolean")
        for key in numbers & row.keys():
            factor(row[key], key)
        if "texCoord" in row:
            integer(row["texCoord"], "texCoord")
    return rows


class GLB:
    """Read only bounded JSON and chunk headers; binary ranges are checked by offsets."""
    def __init__(self, path):
        self.path = path
        self.resources = {}
        self.bin_length = None
        size = path.stat().st_size
        with path.open("rb") as handle:
            header = handle.read(12)
            if len(header) != 12:
                raise ValueError("truncated GLB header")
            magic, version, declared = struct.unpack("<4sII", header)
            if magic != b"glTF" or version != 2 or declared != size or size % 4:
                raise ValueError("invalid GLB magic, version, alignment, or total byte length")
            offset, chunk_number, document = 12, 0, None
            while offset < size:
                raw = handle.read(8)
                if len(raw) != 8:
                    raise ValueError("truncated GLB chunk header")
                length, kind = struct.unpack("<II", raw)
                if length % 4 or offset + 8 + length > size:
                    raise ValueError("invalid or truncated GLB chunk length")
                if chunk_number == 0 and kind != 0x4E4F534A:
                    raise ValueError("first GLB chunk must be JSON")
                if kind == 0x4E4F534A:
                    if document is not None or chunk_number != 0 or not 0 < length <= JSON_LIMIT:
                        raise ValueError("duplicate, misplaced, empty, or oversized GLB JSON chunk")
                    document = decode_json(handle.read(length).decode("utf-8"), "GLB JSON")
                elif kind == 0x004E4942:
                    if self.bin_length is not None or chunk_number != 1:
                        raise ValueError("duplicate or misplaced GLB BIN chunk")
                    self.bin_length = length
                    handle.seek(length, 1)
                else:
                    # glTF permits unknown trailing chunks; their bounds still matter.
                    handle.seek(length, 1)
                offset += 8 + length
                chunk_number += 1
        self.doc = object_value(document, "glTF document")
        asset = object_value(self.doc.get("asset"), "glTF asset")
        if asset.get("version") != "2.0" or asset.get("minVersion", "2.0") != "2.0":
            raise ValueError("only glTF 2.0 is supported")
        for key in ("extensionsUsed", "extensionsRequired"):
            extensions = array(self.doc, key)
            for extension in extensions:
                text(extension, key)
            if len(set(extensions)) != len(extensions):
                raise ValueError(f"duplicate {key} entry")
        if not set(self.doc.get("extensionsRequired", [])).issubset(self.doc.get("extensionsUsed", [])):
            raise ValueError("extensionsRequired must be included in extensionsUsed")
        self.buffers = array(self.doc, "buffers")
        self.views = array(self.doc, "bufferViews")
        self.accessors = array(self.doc, "accessors")
        self.images = array(self.doc, "images")
        self.textures = array(self.doc, "textures")
        self.materials = array(self.doc, "materials")
        self.meshes = array(self.doc, "meshes")
        for index, buffer in enumerate(self.buffers):
            object_value(buffer, "buffer")
            length = integer(buffer.get("byteLength"), "buffer.byteLength", 1)
            if "uri" in buffer:
                resource = self.resource(buffer["uri"], "buffer")
                if resource["byteLength"] < length:
                    raise ValueError(f"buffer {index} exceeds resource bytes")
            elif index != 0 or self.bin_length is None or not length <= self.bin_length <= length + 3:
                raise ValueError(f"buffer {index} has no valid GLB BIN storage")
        if self.bin_length is not None and (not self.buffers or "uri" in self.buffers[0]):
            raise ValueError("GLB BIN chunk has no corresponding buffer 0")
        for index in range(len(self.views)):
            self.view(index)
        # Unselected resources are still part of this delivered GLB's trust boundary.
        for index in range(len(self.images)):
            self.image(index)
        for index in range(len(self.textures)):
            self.texture({"index": index})

    def resource(self, uri, label):
        text(uri, f"{label} URI")
        if uri.startswith("data:"):
            header, separator, encoded = uri.partition(",")
            if not separator or not header.endswith(";base64"):
                raise ValueError("only base64 glTF data URIs are supported")
            media = header[5:-7]
            allowed = ({"application/octet-stream", "application/gltf-buffer"} if label == "buffer"
                       else {"image/png", "image/jpeg", "image/webp", "image/ktx2"})
            if media not in allowed:
                raise ValueError(f"unsupported {label} data URI media type: {media}")
            try:
                data = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ValueError("invalid base64 resource") from exc
            if not data:
                raise ValueError("empty data URI resource")
            return {"storage": "data-uri", "byteLength": len(data), "mimeType": media}
        path = confined_file(self.path.parent, uri, uri=True)
        digest = file_hash(path)
        item = {"path": str(path), "sha256": digest}
        if str(path) in self.resources and self.resources[str(path)] != item:
            raise AuditFailure(f"resource changed during audit: {path}")
        self.resources[str(path)] = item
        return {"storage": "external", "path": str(path), "sha256": digest,
                "byteLength": path.stat().st_size}

    def view(self, index):
        view = indexed(self.views, index, "bufferView")
        buffer = indexed(self.buffers, view.get("buffer"), "bufferView.buffer")
        offset = integer(view.get("byteOffset", 0), "bufferView.byteOffset")
        length = integer(view.get("byteLength"), "bufferView.byteLength", 1)
        if offset + length > buffer["byteLength"]:
            raise ValueError("bufferView exceeds buffer bytes")
        if "byteStride" in view:
            stride = integer(view["byteStride"], "bufferView.byteStride", 4)
            if stride > 252 or stride % 4:
                raise ValueError("invalid bufferView byteStride")
        if "EXT_meshopt_compression" in object_value(view.get("extensions", {}), "bufferView extensions"):
            raise ValueError("compressed bufferViews require separate decoded accessor inspection")
        return view

    def accessor(self, index, semantic):
        accessor = indexed(self.accessors, index, semantic)
        expected = "VEC2" if semantic.startswith("TEXCOORD_") else "VEC3"
        if accessor.get("type") != expected:
            raise ValueError(f"{semantic} accessor must be {expected}")
        component = accessor.get("componentType")
        sizes = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5126: 4}
        if type(component) is not int or component not in sizes:
            raise ValueError(f"invalid {semantic} componentType")
        normalized = accessor.get("normalized", False)
        if type(normalized) is not bool:
            raise ValueError("accessor.normalized must be boolean")
        quantized = "KHR_mesh_quantization" in self.doc.get("extensionsUsed", [])
        if semantic.startswith("TEXCOORD_"):
            allowed = component == 5126 and not normalized or component in (5121, 5123) and normalized
            if not allowed and not (quantized and component != 5126):
                raise ValueError("UV accessor needs floats or normalized unsigned integers (or declared quantization)")
        elif component != 5126 and not quantized:
            raise ValueError("POSITION accessor requires floats or declared quantization")
        count = integer(accessor.get("count"), "accessor.count", 1)
        width = sizes[component] * (2 if expected == "VEC2" else 3)
        offset = integer(accessor.get("byteOffset", 0), "accessor.byteOffset")
        if offset % sizes[component]:
            raise ValueError("misaligned accessor byteOffset")
        if "bufferView" in accessor:
            view = self.view(accessor["bufferView"])
            stride = view.get("byteStride", width)
            if stride < width or stride % sizes[component] or (view.get("byteOffset", 0) + offset) % sizes[component]:
                raise ValueError("invalid accessor stride or alignment")
            if offset + (count - 1) * stride + width > view["byteLength"]:
                raise ValueError(f"{semantic} accessor exceeds bufferView bytes")
        elif offset:
            raise ValueError("accessor without bufferView cannot have byteOffset")
        if "sparse" in accessor:
            sparse = object_value(accessor["sparse"], "sparse accessor")
            sparse_count = integer(sparse.get("count"), "sparse.count", 1)
            if sparse_count > count:
                raise ValueError("sparse accessor count exceeds accessor count")
            for key in ("indices", "values"):
                item = object_value(sparse.get(key), f"sparse.{key}")
                view = self.view(item.get("bufferView"))
                item_width = width
                if key == "indices":
                    if type(item.get("componentType")) is not int or item["componentType"] not in (5121, 5123, 5125):
                        raise ValueError("invalid sparse index componentType")
                    item_width = {5121: 1, 5123: 2, 5125: 4}[item["componentType"]]
                start = integer(item.get("byteOffset", 0), "sparse.byteOffset")
                if "byteStride" in view or start + sparse_count * item_width > view["byteLength"]:
                    raise ValueError("invalid sparse accessor byte range")
        return {"accessor": index, "count": count, "type": expected,
                "componentType": component, "normalized": normalized}

    def image(self, index):
        image = indexed(self.images, index, "texture image")
        if ("uri" in image) == ("bufferView" in image):
            raise ValueError("image must have exactly one of uri or bufferView")
        if "uri" in image:
            return dict(self.resource(image["uri"], "image"), image=index)
        mime = image.get("mimeType")
        if mime not in ("image/png", "image/jpeg", "image/webp", "image/ktx2"):
            raise ValueError("embedded image needs a supported mimeType")
        view = self.view(image["bufferView"])
        if "byteStride" in view:
            raise ValueError("image bufferView cannot be strided")
        return {"image": index, "storage": "bufferView", "bufferView": image["bufferView"],
                "byteLength": view["byteLength"], "mimeType": mime}

    def texture(self, info):
        object_value(info, "textureInfo")
        texture = indexed(self.textures, info.get("index"), "textureInfo.index")
        coord = integer(info.get("texCoord", 0), "textureInfo.texCoord")
        extensions = object_value(info.get("extensions", {}), "textureInfo.extensions")
        if "KHR_texture_transform" in extensions:
            transform = object_value(extensions["KHR_texture_transform"], "texture transform")
            coord = integer(transform.get("texCoord", coord), "texture transform texCoord")
            for key, length in (("offset", 2), ("scale", 2)):
                if key in transform:
                    vector(transform[key], length, f"texture transform {key}", bounded=False)
            if "rotation" in transform and type(transform["rotation"]) not in (int, float):
                raise ValueError("texture transform rotation must be numeric")
        images = []
        if "source" in texture:
            images.append(self.image(texture["source"]))
        tex_extensions = object_value(texture.get("extensions", {}), "texture.extensions")
        for name in ("KHR_texture_basisu", "EXT_texture_webp", "MSFT_texture_dds"):
            if name in tex_extensions:
                if name == "MSFT_texture_dds":
                    raise ValueError("DDS texture source inspection is unsupported")
                ext = object_value(tex_extensions[name], name)
                images.append(dict(self.image(ext.get("source")), extension=name))
        if not images:
            raise ValueError("bound texture has no supported image source")
        if "sampler" in texture:
            indexed(array(self.doc, "samplers"), texture["sampler"], "texture.sampler")
        return {"texture": info["index"], "texCoord": coord, "images": images}


def vector(value, length, label, bounded=True):
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(f"{label} must have {length} components")
    for item in value:
        if bounded:
            factor(item, label)
        elif type(item) not in (int, float):
            raise ValueError(f"{label} components must be numeric")
    return value


def material_maps(material):
    pbr = object_value(material.get("pbrMetallicRoughness", {}), "pbrMetallicRoughness")
    maps = {key: pbr[key] for key in ("baseColorTexture", "metallicRoughnessTexture") if key in pbr}
    maps.update({key: material[key] for key in ("normalTexture", "occlusionTexture", "emissiveTexture") if key in material})
    # Inspect extension textureInfo objects as well, rather than silently ignoring sheen maps.
    for name, extension in object_value(material.get("extensions", {}), "material extensions").items():
        object_value(extension, name)
        for key, info in extension.items():
            if key.endswith("Texture"):
                maps[f"{name}.{key}"] = info
    return pbr, maps


def evaluate(glb_path, policy_path):
    inputs = {"glb": pin(glb_path), "policy": pin(policy_path)}
    policy = validate_policy(read_json(policy_path))
    glb = GLB(glb_path)
    reasons, results = [], []
    names = {}
    for index, material in enumerate(glb.materials):
        object_value(material, "material")
        if "name" in material:
            name = material["name"]
            if not isinstance(name, str):
                raise ValueError("glTF material name must be a string")
            names.setdefault(name, []).append(index)
    primitives = {}
    for mesh_index, mesh in enumerate(glb.meshes):
        object_value(mesh, "mesh")
        rows = mesh.get("primitives")
        if not isinstance(rows, list) or not rows:
            raise ValueError("mesh.primitives must be a nonempty array")
        for primitive_index, primitive in enumerate(rows):
            object_value(primitive, "primitive")
            if "material" in primitive:
                index = primitive["material"]
                indexed(glb.materials, index, "primitive.material")
                primitives.setdefault(index, []).append((mesh_index, primitive_index, primitive))
    for rule in policy:
        name = rule["name"]
        matches = names.get(name, [])
        if len(matches) != 1:
            reasons.append(f"{name}: expected exactly one material target; found {len(matches)}")
            continue
        index = matches[0]
        material = glb.materials[index]
        pbr, maps = material_maps(material)
        roughness = factor(pbr.get("roughnessFactor", 1), "roughnessFactor")
        metallic = factor(pbr.get("metallicFactor", 1), "metallicFactor")
        base_color = vector(pbr.get("baseColorFactor", [1, 1, 1, 1]), 4, "baseColorFactor")
        sheen = object_value(material.get("extensions", {}).get("KHR_materials_sheen", {}), "sheen")
        sheen_color = vector(sheen.get("sheenColorFactor", [0, 0, 0]), 3, "sheenColorFactor")
        sheen_roughness = factor(sheen.get("sheenRoughnessFactor", 0), "sheenRoughnessFactor")
        bound = {key: glb.texture(info) for key, info in maps.items()}
        if "normalTexture" in maps:
            scale = maps["normalTexture"].get("scale", 1)
            if type(scale) not in (int, float):
                raise ValueError("normalTexture.scale must be a finite number")
            bound["normalTexture"]["scale"] = scale
        if "occlusionTexture" in maps:
            bound["occlusionTexture"]["strength"] = factor(maps["occlusionTexture"].get("strength", 1), "occlusion strength")
        for requirement, map_key in (("requireBaseColorTexture", "baseColorTexture"),
                                     ("requireNormalTexture", "normalTexture"),
                                     ("requireRoughnessTexture", "metallicRoughnessTexture")):
            if rule.get(requirement) is True and map_key not in bound:
                reasons.append(f"{name}: required {map_key} is not bound")
        if "minRoughnessFactor" in rule and roughness < rule["minRoughnessFactor"]:
            reasons.append(f"{name}: roughnessFactor {roughness} is below declared minimum")
        if "maxMetallicFactor" in rule and metallic > rule["maxMetallicFactor"]:
            reasons.append(f"{name}: metallicFactor {metallic} exceeds declared maximum")
        if "maxSheenColorFactor" in rule and max(sheen_color) > rule["maxSheenColorFactor"]:
            reasons.append(f"{name}: sheenColorFactor {sheen_color} exceeds declared maximum")
        uses = primitives.get(index, [])
        if not uses:
            reasons.append(f"{name}: selected material is not bound to any mesh primitive")
        primitive_results = []
        for mesh_index, primitive_index, primitive in uses:
            if "KHR_draco_mesh_compression" in object_value(primitive.get("extensions", {}), "primitive extensions"):
                raise ValueError("Draco primitive inspection requires decoded geometry")
            attributes = object_value(primitive.get("attributes"), "primitive attributes")
            position = glb.accessor(attributes.get("POSITION"), "POSITION")
            needed = {item["texCoord"] for item in bound.values()}
            if "texCoord" in rule:
                needed.add(rule["texCoord"])
                for key, item in bound.items():
                    if item["texCoord"] != rule["texCoord"]:
                        reasons.append(f"{name}: {key} uses TEXCOORD_{item['texCoord']}, policy requires TEXCOORD_{rule['texCoord']}")
            uvs = {}
            for coord in sorted(needed):
                semantic = f"TEXCOORD_{coord}"
                if semantic not in attributes:
                    reasons.append(f"{name}: mesh {mesh_index} primitive {primitive_index} lacks {semantic}")
                    continue
                uv = glb.accessor(attributes[semantic], semantic)
                if uv["count"] != position["count"]:
                    raise ValueError(f"{name}: {semantic} count does not match POSITION")
                uvs[semantic] = uv
            primitive_results.append({"mesh": mesh_index, "primitive": primitive_index, "uvAttributes": uvs})
        results.append({"name": name, "material": index, "expectations": rule,
                        "factors": {"roughnessFactor": roughness, "metallicFactor": metallic,
                                    "baseColorFactor": base_color, "sheenColorFactor": sheen_color,
                                    "sheenRoughnessFactor": sheen_roughness},
                        "textures": bound, "primitives": primitive_results})
    for label, value in inputs.items():
        check_pin(value, label)
    for resource in glb.resources.values():
        check_pin(resource, "external resource")
    return {"schemaVersion": 1, "audit": GATE, "passed": not reasons, "reasons": reasons,
            "inputs": inputs, "resources": sorted(glb.resources.values(), key=lambda item: item["path"]),
            "materials": results, "texturePixelsEvaluated": False, "limitations": LIMITATIONS}


def gate(workspace):
    receipt = load_receipt(workspace, RECEIPT, STATE_KEY)
    if receipt.get("audit") != GATE:
        raise ValueError("wrong audit receipt kind")
    inputs = fields(receipt.get("inputs"), ["glb", "policy"], [], "receipt.inputs")
    glb = check_pin(inputs["glb"], "GLB")
    policy = check_pin(inputs["policy"], "policy")
    resources = receipt.get("resources")
    if not isinstance(resources, list):
        raise ValueError("receipt resources must be an array")
    for resource in resources:
        check_pin(resource, "external resource")
    current = evaluate(glb, policy)
    if current["resources"] != resources:
        raise AuditFailure("external resource bindings changed since audit")
    if not receipt["passed"]:
        current["passed"] = False
        current["reasons"].append("stored material audit was negative; run the normal audit after repair")
    return current


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    gate_mode = "--gate" in argv
    try:
        parser = Parser(description=__doc__)
        parser.add_argument("--workspace", required=True)
        parser.add_argument("--glb")
        parser.add_argument("--policy")
        parser.add_argument("--gate", action="store_true")
        args = parser.parse_args(argv)
        workspace = workspace_path(args.workspace)
        if args.gate:
            if args.glb or args.policy:
                raise ValueError("--gate reads pinned inputs; do not supply --glb or --policy")
            report = gate(workspace)
        else:
            if not args.glb or not args.policy:
                raise ValueError("normal audit requires --glb and --policy")
            report = evaluate(input_path(args.glb), input_path(args.policy))
            persist(workspace, RECEIPT, STATE_KEY, report)
        return emit(GATE, "pass" if report["passed"] else "fail", report["reasons"], report, gate_mode=gate_mode)
    except AuditFailure as exc:
        return emit(GATE, "fail", [str(exc)], {}, gate_mode=gate_mode)
    except (ValueError, OSError, RuntimeError, RecursionError) as exc:
        return emit(GATE, "error", [str(exc)], {}, gate_mode=gate_mode)


if __name__ == "__main__":
    sys.exit(main())
