import * as THREE from 'three';
import { validateRoomBounds } from './interior-manifest.js';

export function createInteriorNavigation(camera, controls, roomBounds) {
  validateRoomBounds(roomBounds);
  const room = new THREE.Box3(
    new THREE.Vector3().fromArray(roomBounds.min),
    new THREE.Vector3().fromArray(roomBounds.max),
  );
  const cameraBounds = room.clone().expandByScalar(-0.2);
  const targetBounds = room.clone();
  targetBounds.min.add(new THREE.Vector3(0.2, 0, 0.2));
  targetBounds.max.sub(new THREE.Vector3(0.2, 0.15, 0.2));
  const previousCamera = new THREE.Vector3();
  const previousTarget = new THREE.Vector3();
  const direction = new THREE.Vector3();
  const center = room.getCenter(new THREE.Vector3());
  const originalUpdate = controls.update;
  const originalLimits = { minDistance: controls.minDistance, maxDistance: controls.maxDistance,
    minPolarAngle: controls.minPolarAngle, maxPolarAngle: controls.maxPolarAngle };
  const size = room.getSize(new THREE.Vector3());
  let disposed = false;
  let atBoundary = false;

  controls.minDistance = Math.min(0.3, (Math.min(size.x, size.y, size.z)-0.4)/2);
  controls.maxDistance = size.length();
  controls.minPolarAngle = 0.02;
  controls.maxPolarAngle = Math.PI - 0.02;

  function constrain() {
    if (disposed) return false;
    previousCamera.copy(camera.position);
    previousTarget.copy(controls.target);
    cameraBounds.clampPoint(camera.position, camera.position);
    targetBounds.clampPoint(controls.target, controls.target);

    if (camera.position.distanceToSquared(controls.target) < controls.minDistance ** 2) {
      direction.subVectors(controls.target, camera.position);
      if (direction.lengthSq() > 1e-12) {
        direction.normalize();
        controls.target.copy(camera.position).addScaledVector(direction, controls.minDistance);
        targetBounds.clampPoint(controls.target, controls.target);
      }
      if (camera.position.distanceToSquared(controls.target) < controls.minDistance ** 2) {
        // Near floor/ceiling, a vertical ray may have no room. Aim horizontally
        // into the room instead of pushing the eye through the shell.
        direction.set(center.x-camera.position.x, 0, center.z-camera.position.z);
        if (direction.lengthSq() < 1e-12) direction.set(0, 0, -1);
        direction.normalize();
        controls.target.copy(camera.position).addScaledVector(direction, controls.minDistance);
        targetBounds.clampPoint(controls.target, controls.target);
      }
    }

    atBoundary = !camera.position.equals(previousCamera) || !controls.target.equals(previousTarget);
    if (atBoundary) camera.lookAt(controls.target);
    // OrbitControls r180 derives spherical coordinates from the actual eye and
    // target at the next update; its current change dispatch commits these final
    // transforms afterwards. Calling update here would reintroduce an escape.
    return atBoundary;
  }

  function updateWithinRoom(deltaTime) {
    atBoundary = false;
    const changed = originalUpdate.call(controls, deltaTime);
    const eventBoundary = atBoundary;
    // r180 can skip `change` for sub-EPS transforms. Clamp those too.
    const finalBoundary = constrain();
    atBoundary = eventBoundary || finalBoundary;
    return changed || atBoundary;
  }

  controls.update = updateWithinRoom;
  controls.addEventListener('change', constrain);
  constrain();
  return {
    constrain,
    snapshot() {
      const distance = camera.position.distanceTo(controls.target);
      return {
        bounds: { min: room.min.toArray(), max: room.max.toArray(), cameraMargin: 0.2,
          targetWallMargin: 0.2, targetCeilingMargin: 0.15 },
        camera: camera.position.toArray(), target: controls.target.toArray(),
        safety: {
          cameraInBounds: cameraBounds.containsPoint(camera.position),
          targetInBounds: targetBounds.containsPoint(controls.target),
          distance,
          polarAngle: distance ? Math.acos(THREE.MathUtils.clamp((camera.position.y-controls.target.y)/distance, -1, 1)) : null,
          atBoundary,
          minDistance: controls.minDistance, maxDistance: controls.maxDistance,
        },
      };
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      controls.removeEventListener('change', constrain);
      if (controls.update === updateWithinRoom) {
        controls.update = originalUpdate;
        Object.assign(controls, originalLimits);
      }
    },
  };
}
