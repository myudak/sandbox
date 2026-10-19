import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { engine } from '../sim/engine';

const MAX = 48;

const vertex = /* glsl */ `
  uniform float uTime;
  uniform int uCount;
  uniform float uAmp[${MAX}];
  uniform float uOmega[${MAX}];
  uniform float uK[${MAX}];
  uniform float uPhase[${MAX}];
  varying vec3 vWorld;
  varying vec3 vNormal;
  void main() {
    vec4 world = modelMatrix * vec4(position, 1.0);
    float h = 0.0;
    float dhdx = 0.0;
    for (int i = 0; i < ${MAX}; i++) {
      if (i >= uCount) break;
      float arg = uOmega[i] * uTime - uK[i] * world.x + uPhase[i];
      h += uAmp[i] * cos(arg);
      dhdx += uAmp[i] * uK[i] * sin(arg);
    }
    world.y += h;
    vWorld = world.xyz;
    vNormal = normalize(vec3(-dhdx, 1.0, 0.0));
    gl_Position = projectionMatrix * viewMatrix * world;
  }
`;

const fragment = /* glsl */ `
  uniform vec3 uDeep;
  uniform vec3 uShallow;
  uniform vec3 uSky;
  uniform vec3 uSun;
  varying vec3 vWorld;
  varying vec3 vNormal;
  void main() {
    vec3 n = normalize(vNormal);
    vec3 v = normalize(cameraPosition - vWorld);
    bool below = cameraPosition.y < vWorld.y;
    if (below) n = -n;
    float fres = pow(1.0 - max(dot(n, v), 0.0), 4.0);
    vec3 col = mix(uDeep, uShallow, 0.35 + 0.4 * max(n.y, 0.0));
    col = mix(col, uSky, below ? 0.0 : fres * 0.8);
    vec3 h = normalize(v + normalize(uSun));
    col += below ? vec3(0.0) : vec3(1.0, 0.95, 0.85) * pow(max(dot(n, h), 0.0), 220.0) * 1.4;
    float dist = length(vWorld.xz - cameraPosition.xz);
    float alpha = below ? 0.55 : mix(0.72, 0.97, fres);
    alpha *= 1.0 - smoothstep(1100.0, 1500.0, dist);
    gl_FragColor = vec4(col, alpha);
  }
`;

/** Sea surface rendered from the same wave components that force the physics (largest 48). */
export function Ocean() {
  const mat = useRef<THREE.ShaderMaterial>(null);
  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uCount: { value: 0 },
      uAmp: { value: new Array(MAX).fill(0) },
      uOmega: { value: new Array(MAX).fill(0) },
      uK: { value: new Array(MAX).fill(0) },
      uPhase: { value: new Array(MAX).fill(0) },
      uDeep: { value: new THREE.Color('#0a3346') },
      uShallow: { value: new THREE.Color('#1d6f86') },
      uSky: { value: new THREE.Color('#b9d3e4') },
      uSun: { value: new THREE.Vector3(-0.4, 0.6, 0.5) },
    }),
    [],
  );
  const loaded = useRef(-1);
  useFrame(() => {
    const u = uniforms;
    if (loaded.current !== engine.version) {
      loaded.current = engine.version;
      const comps = [...engine.waves].sort((a, b) => b.amp - a.amp).slice(0, MAX);
      u.uCount.value = comps.length;
      comps.forEach((c, i) => {
        u.uAmp.value[i] = c.amp;
        u.uOmega.value[i] = c.omega;
        u.uK.value[i] = c.k;
        u.uPhase.value[i] = c.phase;
      });
    }
    u.uTime.value = engine.t;
  });
  return (
    <mesh rotation-x={-Math.PI / 2} renderOrder={2}>
      <planeGeometry args={[3200, 3200, 320, 320]} />
      <shaderMaterial
        ref={mat}
        vertexShader={vertex}
        fragmentShader={fragment}
        uniforms={uniforms}
        transparent
        depthWrite={false}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}
