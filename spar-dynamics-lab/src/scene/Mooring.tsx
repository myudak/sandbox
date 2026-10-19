import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { OC3_HYWIND } from '../physics/params';
import { HEAVE, PITCH, SURGE } from '../physics/model';
import { engine } from '../sim/engine';
import { useApp } from '../state/store';
import { catenaryPoints } from './catenary';

const G = OC3_HYWIND.mooringGeometry;
const SEABED = -OC3_HYWIND.waterDepth;
const N = 48;
// OC3 lines point upwind (180°) and at ±60° downwind
const HEADINGS = [Math.PI, Math.PI / 3, -Math.PI / 3];

/** Three catenary lines whose fairleads follow the TMD platform's pose. */
export function Mooring() {
  const lines = useMemo(
    () =>
      HEADINGS.map(() => {
        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array((N + 1) * 3), 3));
        return geo;
      }),
    [],
  );
  const mat = useMemo(() => new THREE.LineBasicMaterial({ color: '#c9b37a' }), []);
  const objs = useMemo(() => lines.map((g) => new THREE.Line(g, mat)), [lines, mat]);
  const frame = useRef(0);

  useFrame(() => {
    if (!engine.tmd || frame.current++ % 2) return;
    const ex = useApp.getState().exaggeration;
    const x = engine.tmd.sim.position();
    const th = -x[PITCH] * ex;
    HEADINGS.forEach((h, i) => {
      // fairlead in the body frame, then rotated by pitch about SWL
      const bx = G.fairleadRadius * Math.cos(h);
      const bz = G.fairleadRadius * Math.sin(h);
      const by = -G.fairleadDepth;
      const fx = x[SURGE] * ex + bx * Math.cos(th) - by * Math.sin(th);
      const fy = x[HEAVE] * ex + bx * Math.sin(th) + by * Math.cos(th);
      const fz = bz;
      const ax = G.anchorRadius * Math.cos(h);
      const az = G.anchorRadius * Math.sin(h);
      const span = Math.hypot(fx - ax, fz - az);
      const pts = catenaryPoints(span, fy - SEABED, G.unstretchedLength, N);
      const ux = (fx - ax) / span;
      const uz = (fz - az) / span;
      const arr = lines[i].attributes.position.array as Float32Array;
      pts.forEach(([s, y], k) => {
        arr[k * 3] = ax + ux * s;
        arr[k * 3 + 1] = SEABED + y;
        arr[k * 3 + 2] = az + uz * s;
      });
      lines[i].attributes.position.needsUpdate = true;
    });
  });

  return (
    <group>
      {objs.map((o, i) => (
        <primitive key={i} object={o} />
      ))}
      {HEADINGS.map((h, i) => (
        <mesh key={i} position={[G.anchorRadius * Math.cos(h), SEABED + 2, G.anchorRadius * Math.sin(h)]}>
          <boxGeometry args={[8, 4, 8]} />
          <meshStandardMaterial color="#5b5446" />
        </mesh>
      ))}
    </group>
  );
}

export function Seabed() {
  return (
    <mesh rotation-x={-Math.PI / 2} position={[0, SEABED, 0]} receiveShadow>
      <circleGeometry args={[1500, 64]} />
      <meshStandardMaterial color="#3a3a2c" roughness={1} />
    </mesh>
  );
}
