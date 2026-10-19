import { useEffect, useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { OC3_HYWIND } from '../physics/params';
import { DAMPER, HEAVE, PITCH, SURGE } from '../physics/model';
import { engine, Run } from '../sim/engine';
import { useApp } from '../state/store';

const P = OC3_HYWIND;

function hullProfile(): THREE.Vector2[] {
  const pts: [number, number][] = [
    [0, P.towerBaseZ],
    [3.25, P.towerBaseZ],
    [3.25, -4],
    [4.7, -12],
    [4.7, -119],
    [4.2, -120],
    [0, -120],
  ];
  return pts.map(([r, y]) => new THREE.Vector2(r, y)).reverse();
}

interface Props {
  which: 'base' | 'tmd';
  ghost?: boolean;
}

/**
 * The floating turbine: spar hull, tower, nacelle, rotor and (for the TMD
 * run) the rotary damper. Pose is read from the engine every frame.
 */
export function Turbine({ which, ghost = false }: Props) {
  const root = useRef<THREE.Group>(null);
  const rotor = useRef<THREE.Group>(null);
  const damper = useRef<THREE.Group>(null);
  const cutaway = useApp((s) => s.cutaway);
  const tmd = useApp((s) => s.tmd);

  const hullGeo = useMemo(() => new THREE.LatheGeometry(hullProfile(), 48), []);
  const towerH = P.towerTopZ - P.towerBaseZ;

  const mats = useMemo(() => {
    const ghostMat = new THREE.MeshStandardMaterial({
      color: '#d95926',
      transparent: true,
      opacity: 0.28,
      depthWrite: false,
      roughness: 0.6,
    });
    if (ghost) return { hull: ghostMat, band: ghostMat, tower: ghostMat, nacelle: ghostMat, blade: ghostMat };
    return {
      hull: new THREE.MeshStandardMaterial({ color: '#7a2b22', roughness: 0.7, metalness: 0.2 }),
      band: new THREE.MeshStandardMaterial({ color: '#e0ad1f', roughness: 0.5 }),
      tower: new THREE.MeshStandardMaterial({ color: '#dfe3e6', roughness: 0.45, metalness: 0.1 }),
      nacelle: new THREE.MeshStandardMaterial({ color: '#f1f3f4', roughness: 0.4 }),
      blade: new THREE.MeshStandardMaterial({ color: '#f5f6f7', roughness: 0.35 }),
    };
  }, [ghost]);

  // nacelle opacity tracks the cutaway toggle (solid turbine only)
  useEffect(() => {
    if (ghost) return;
    mats.nacelle.transparent = cutaway;
    mats.nacelle.opacity = cutaway ? 0.18 : 1;
    mats.nacelle.depthWrite = !cutaway;
    mats.nacelle.needsUpdate = true;
  }, [cutaway, ghost, mats]);

  const damperRadius = Math.cbrt((3 * (tmd.mass / 7850)) / (4 * Math.PI));

  useFrame(() => {
    const run: Run | null = which === 'base' ? engine.base : engine.tmd;
    if (!run || !root.current) return;
    const ex = useApp.getState().exaggeration;
    const x = run.sim.position();
    root.current.position.set(x[SURGE] * ex, x[HEAVE] * ex, 0);
    root.current.rotation.z = -x[PITCH] * ex;
    if (rotor.current) rotor.current.rotation.x = engine.rotorAngle;
    if (damper.current && x.length > DAMPER) damper.current.rotation.z = -x[DAMPER];
  });

  return (
    <group ref={root}>
      <mesh geometry={hullGeo} material={mats.hull} castShadow />
      <mesh position={[0, 3, 0]} material={mats.band}>
        <cylinderGeometry args={[3.3, 3.3, 14, 48, 1, true]} />
      </mesh>
      <mesh position={[0, P.towerBaseZ + towerH / 2, 0]} material={mats.tower} castShadow>
        <cylinderGeometry args={[P.towerTopDiameter / 2, P.towerBaseDiameter / 2, towerH, 32]} />
      </mesh>
      {/* nacelle: ~14 m long, upwind rotor at x = −5 m */}
      <mesh position={[3, P.towerTopZ + 2.2, 0]} material={mats.nacelle}>
        <boxGeometry args={[14, 4.4, 4.4]} />
      </mesh>
      <group ref={rotor} position={[-5, P.hubHeight, 0]}>
        <mesh material={mats.nacelle} rotation-z={Math.PI / 2}>
          <sphereGeometry args={[1.8, 20, 16]} />
        </mesh>
        {[0, 1, 2].map((i) => (
          <group key={i} rotation-x={(i * 2 * Math.PI) / 3}>
            <mesh position={[0, 32, 0]} material={mats.blade}>
              <boxGeometry args={[0.6, 61.5, 2.8]} />
            </mesh>
          </group>
        ))}
      </group>
      {which === 'tmd' && (
        <group ref={damper} position={[0, tmd.pivotZ, 0]}>
          <mesh rotation-x={Math.PI / 2}>
            <cylinderGeometry args={[0.7, 0.7, 2.2, 24]} />
            <meshStandardMaterial color="#9aa3ab" metalness={0.6} roughness={0.3} transparent={ghost} opacity={ghost ? 0.3 : 1} />
          </mesh>
          <mesh position={[0, -tmd.arm / 2, 0]}>
            <boxGeometry args={[0.35, Math.abs(tmd.arm) || 0.01, 0.35]} />
            <meshStandardMaterial color="#c8ced3" metalness={0.5} roughness={0.35} />
          </mesh>
          <mesh position={[0, -tmd.arm, 0]}>
            <sphereGeometry args={[Math.max(damperRadius, tmd.gyration * 0.6), 28, 20]} />
            <meshStandardMaterial color="#3987e5" emissive="#1c5cab" emissiveIntensity={0.6} metalness={0.4} roughness={0.3} />
          </mesh>
        </group>
      )}
    </group>
  );
}
