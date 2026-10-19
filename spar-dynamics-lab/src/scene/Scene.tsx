import { useEffect, useRef } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, Sky } from '@react-three/drei';
import * as THREE from 'three';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import { Ocean } from './Ocean';
import { Turbine } from './Turbine';
import { Mooring, Seabed } from './Mooring';
import { engine } from '../sim/engine';
import { CameraPreset, useApp } from '../state/store';

const PRESETS: Record<CameraPreset, { pos: [number, number, number]; target: [number, number, number] }> = {
  overview: { pos: [-260, 95, 330], target: [0, 45, 0] },
  waterline: { pos: [-55, 6, 75], target: [0, 5, 0] },
  underwater: { pos: [-150, -80, 200], target: [0, -65, 0] },
  nacelle: { pos: [24, 94, 19], target: [1, 89, 0] },
};

const ABOVE_FOG = new THREE.FogExp2('#a9c3d3', 0.00045);
const BELOW_FOG = new THREE.FogExp2('#0a3a4e', 0.0026);
const ABOVE_BG = new THREE.Color('#a9c3d3');
const BELOW_BG = new THREE.Color('#062433');

/** Drives the simulation clock, the camera presets and the above/below-water look. */
function Director() {
  const { camera, scene } = useThree();
  const controls = useThree((s) => s.controls) as OrbitControlsImpl | null;
  const nonce = useApp((s) => s.cameraNonce);
  const anim = useRef<{ t: number; from: THREE.Vector3; to: THREE.Vector3; tf: THREE.Vector3; tt: THREE.Vector3 } | null>(null);

  useEffect(() => {
    if (!controls) return;
    const p = PRESETS[useApp.getState().camera];
    anim.current = {
      t: 0,
      from: camera.position.clone(),
      to: new THREE.Vector3(...p.pos),
      tf: controls.target.clone(),
      tt: new THREE.Vector3(...p.target),
    };
  }, [nonce, controls, camera]);

  useFrame((_, dt) => {
    const s = useApp.getState();
    if (!s.paused) engine.advance(dt, s.timeScale);
    const a = anim.current;
    if (a && controls) {
      a.t = Math.min(1, a.t + dt / 1.2);
      const k = a.t * a.t * (3 - 2 * a.t);
      camera.position.lerpVectors(a.from, a.to, k);
      controls.target.lerpVectors(a.tf, a.tt, k);
      controls.update();
      if (a.t >= 1) anim.current = null;
    }
    const below = camera.position.y < 0;
    scene.fog = below ? BELOW_FOG : ABOVE_FOG;
    scene.background = below ? BELOW_BG : ABOVE_BG;
    const sky = scene.getObjectByName('sky');
    if (sky) sky.visible = !below;
  });
  return null;
}

export function Scene() {
  const primary = useApp((s) => s.primary);
  const ghost = useApp((s) => s.ghost);
  const other = primary === 'tmd' ? 'base' : 'tmd';
  return (
    <Canvas
      camera={{ position: PRESETS.overview.pos, fov: 45, near: 0.5, far: 6000 }}
      dpr={[1, 2]}
      gl={{ antialias: true }}
    >
      <Director />
      <group name="sky">
        <Sky distance={4500} sunPosition={[-400, 600, 500]} turbidity={6} rayleigh={1.4} />
      </group>
      <hemisphereLight args={['#dfeaf2', '#20313a', 0.9]} />
      <directionalLight position={[-400, 600, 500]} intensity={1.6} />
      <Ocean />
      <Turbine which={primary} />
      {ghost && <Turbine which={other} ghost />}
      <Mooring />
      <Seabed />
      <OrbitControls makeDefault target={PRESETS.overview.target} maxDistance={2200} minDistance={5} />
    </Canvas>
  );
}
