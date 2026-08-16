import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { Compass, RotateCw } from 'lucide-react';

interface Gimbal3DViewProps {
  pitch: number; // in degrees
  yaw: number;   // in degrees
  roll?: number;
  laserFiring: boolean;
  laserArmed: boolean;
  systemState?: string;
}

export const Gimbal3DView: React.FC<Gimbal3DViewProps> = ({
  pitch,
  yaw,
  roll = 0,
  laserFiring,
  laserArmed,
  systemState,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);

  // Gimbal 3D Nodes
  const yawGroupRef = useRef<THREE.Group | null>(null);
  const pitchGroupRef = useRef<THREE.Group | null>(null);
  const laserBeamRef = useRef<THREE.Mesh | null>(null);
  const laserGlowRef = useRef<THREE.PointLight | null>(null);

  // Mouse drag Orbit state
  const isDraggingRef = useRef<boolean>(false);
  const previousMousePosition = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const cameraAngle = useRef<{ phi: number; theta: number }>({ phi: Math.PI / 3.4, theta: Math.PI / 3.2 });
  const cameraRadius = useRef<number>(6.5);

  const resetCamera = () => {
    cameraAngle.current = { phi: Math.PI / 3.4, theta: Math.PI / 3.2 };
    cameraRadius.current = 6.5;
    updateCameraPosition();
  };

  const updateCameraPosition = () => {
    if (!cameraRef.current) return;
    const { phi, theta } = cameraAngle.current;
    const r = cameraRadius.current;

    cameraRef.current.position.x = r * Math.sin(phi) * Math.sin(theta);
    cameraRef.current.position.y = r * Math.cos(phi);
    cameraRef.current.position.z = r * Math.sin(phi) * Math.cos(theta);
    cameraRef.current.lookAt(0, 0.4, 0);
  };

  useEffect(() => {
    if (!containerRef.current) return;

    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;

    // 1. Scene
    const scene = new THREE.Scene();
    sceneRef.current = scene;

    // 2. Camera
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    cameraRef.current = camera;
    updateCameraPosition();

    // 3. Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    rendererRef.current = renderer;

    containerRef.current.replaceChildren(renderer.domElement);

    // 4. Studio & Tactical Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 2.2);
    scene.add(ambientLight);

    const keyLight = new THREE.DirectionalLight(0xfff5e6, 3.5);
    keyLight.position.set(6, 9, 6);
    scene.add(keyLight);

    const rimLight = new THREE.DirectionalLight(0x00f0ff, 2.2);
    rimLight.position.set(-6, 4, -5);
    scene.add(rimLight);

    const warmUnderLight = new THREE.PointLight(0xf59e0b, 2.8, 10);
    warmUnderLight.position.set(0, -0.3, 2);
    scene.add(warmUnderLight);

    // 5. Grid Ground & Range Rings
    const gridHelper = new THREE.GridHelper(12, 24, 0xf59e0b, 0x1e293b);
    gridHelper.position.y = -0.01;
    scene.add(gridHelper);

    // Azimuth Target Ring
    const ringGeo = new THREE.RingGeometry(2.8, 2.85, 64);
    const ringMat = new THREE.MeshBasicMaterial({ color: 0xf59e0b, side: THREE.DoubleSide, transparent: true, opacity: 0.35 });
    const ringMesh = new THREE.Mesh(ringGeo, ringMat);
    ringMesh.rotation.x = -Math.PI / 2;
    ringMesh.position.y = 0.01;
    scene.add(ringMesh);

    // =========================================================================
    // 6. Gimbal Model (Camera Optical Axis Length = 40cm, Width = 10cm, Height = 8cm)
    // Scale: 1 unit = 10 cm (40cm = 4.0u Z-Length, 10cm = 1.0u X-Width, 8cm = 0.8u Y-Height)
    // Color: Industrial Tactical Yellow (#F59E0B / #EAB308)
    // =========================================================================

    // Tactical Yellow Material
    const yellowGimbalMat = new THREE.MeshStandardMaterial({
      color: 0xf59e0b,       // Industrial Tactical Yellow
      metalness: 0.35,
      roughness: 0.28,
      emissive: 0x3d2400,
    });

    // Dark Carbon/Metallic Material
    const darkMetalMat = new THREE.MeshStandardMaterial({
      color: 0x18181b,
      metalness: 0.85,
      roughness: 0.2,
      emissive: 0x09090b,
    });

    // Accent Gold/Yellow Rim Material
    const accentRimMat = new THREE.MeshBasicMaterial({ color: 0xffd000 });

    // [A. Fixed Base Mount Pedestal]
    const basePlateGeo = new THREE.CylinderGeometry(0.7, 0.85, 0.12, 32);
    const basePlate = new THREE.Mesh(basePlateGeo, darkMetalMat);
    basePlate.position.y = 0.06;
    scene.add(basePlate);

    const baseRimGeo = new THREE.TorusGeometry(0.72, 0.015, 16, 64);
    const baseRim = new THREE.Mesh(baseRimGeo, accentRimMat);
    baseRim.rotation.x = Math.PI / 2;
    baseRim.position.y = 0.12;
    scene.add(baseRim);

    // [B. Yaw Rotating Assembly (Bearing Hub + Upright Fork)]
    const yawGroup = new THREE.Group();
    yawGroup.position.y = 0.12;
    scene.add(yawGroup);
    yawGroupRef.current = yawGroup;

    // Yaw Hub Center
    const yawHubGeo = new THREE.CylinderGeometry(0.65, 0.65, 0.12, 32);
    const yawHub = new THREE.Mesh(yawHubGeo, yellowGimbalMat);
    yawHub.position.y = 0.06;
    yawGroup.add(yawHub);

    // Fork Base Support (Width 1.2u = 12cm, Depth 0.8u, Height 0.12u)
    const forkBaseGeo = new THREE.BoxGeometry(1.28, 0.12, 0.8);
    const forkBase = new THREE.Mesh(forkBaseGeo, yellowGimbalMat);
    forkBase.position.y = 0.12;
    yawGroup.add(forkBase);

    // Left Yoke Arm (Holds 10cm wide pod)
    const armGeo = new THREE.BoxGeometry(0.12, 0.58, 0.55);
    const leftArm = new THREE.Mesh(armGeo, yellowGimbalMat);
    leftArm.position.set(-0.58, 0.38, 0);
    yawGroup.add(leftArm);

    // Right Yoke Arm
    const rightArm = new THREE.Mesh(armGeo, yellowGimbalMat);
    rightArm.position.set(0.58, 0.38, 0);
    yawGroup.add(rightArm);

    // Precision Axis Pivot Caps
    const pivotGeo = new THREE.CylinderGeometry(0.15, 0.15, 0.16, 24);
    pivotGeo.rotateZ(Math.PI / 2);
    const leftPivot = new THREE.Mesh(pivotGeo, darkMetalMat);
    leftPivot.position.set(-0.59, 0.52, 0);
    yawGroup.add(leftPivot);
    const rightPivot = new THREE.Mesh(pivotGeo, darkMetalMat);
    rightPivot.position.set(0.59, 0.52, 0);
    yawGroup.add(rightPivot);

    // [C. Pitch Rotating Assembly: 40cm Long Optical Tube / Camera Barrel]
    // Width X = 1.0 (10cm), Height Y = 0.56 (fits in 8cm total), Length Z = 4.0 (40cm!)
    const pitchGroup = new THREE.Group();
    pitchGroup.position.set(0, 0.52, 0);
    yawGroup.add(pitchGroup);
    pitchGroupRef.current = pitchGroup;

    // Main 40cm Elongated Optical & Laser Housing Body
    const podGeo = new THREE.BoxGeometry(0.96, 0.52, 3.9);
    const podMesh = new THREE.Mesh(podGeo, yellowGimbalMat);
    pitchGroup.add(podMesh);

    // Tactical Cooling Ribs along the 40cm Body (Z-Axis)
    for (let z = -1.5; z <= 1.5; z += 0.4) {
      const ribGeo = new THREE.BoxGeometry(1.02, 0.54, 0.06);
      const ribMesh = new THREE.Mesh(ribGeo, darkMetalMat);
      ribMesh.position.set(0, 0, z);
      pitchGroup.add(ribMesh);
    }

    // Front Faceplate (Z = +1.95)
    const frontFaceGeo = new THREE.BoxGeometry(0.92, 0.48, 0.08);
    const frontFace = new THREE.Mesh(frontFaceGeo, darkMetalMat);
    frontFace.position.set(0, 0, 1.96);
    pitchGroup.add(frontFace);

    // Center High-Power Laser Emitter Barrel (Protrudes at Z = +2.0 to +2.3)
    const barrelGeo = new THREE.CylinderGeometry(0.12, 0.14, 0.5, 32);
    barrelGeo.rotateX(Math.PI / 2);
    const barrelMesh = new THREE.Mesh(barrelGeo, darkMetalMat);
    barrelMesh.position.set(0, 0.08, 2.15);
    pitchGroup.add(barrelMesh);

    // Laser Aperture Red Glow Ring
    const laserApertureGeo = new THREE.TorusGeometry(0.12, 0.018, 16, 32);
    const laserApertureMat = new THREE.MeshBasicMaterial({ color: 0xff2233 });
    const laserAperture = new THREE.Mesh(laserApertureGeo, laserApertureMat);
    laserAperture.position.set(0, 0.08, 2.4);
    pitchGroup.add(laserAperture);

    // Dual Optical Camera Lenses (Left: Primary 1080P EO Sensor, Right: IR / Color Sensor)
    const camLensGeo = new THREE.CylinderGeometry(0.085, 0.085, 0.25, 24);
    camLensGeo.rotateX(Math.PI / 2);
    const camLensMat = new THREE.MeshStandardMaterial({ color: 0x00f0ff, emissive: 0x005577, roughness: 0.1 });

    const leftLens = new THREE.Mesh(camLensGeo, camLensMat);
    leftLens.position.set(-0.28, -0.08, 2.05);
    pitchGroup.add(leftLens);

    const rightLens = new THREE.Mesh(camLensGeo, camLensMat);
    rightLens.position.set(0.28, -0.08, 2.05);
    pitchGroup.add(rightLens);

    // Rear Cooling Exhaust Cap (Z = -2.0)
    const rearCapGeo = new THREE.BoxGeometry(0.92, 0.48, 0.1);
    const rearCap = new THREE.Mesh(rearCapGeo, darkMetalMat);
    rearCap.position.set(0, 0, -1.98);
    pitchGroup.add(rearCap);

    // [D. Laser Beam Effect (Originates from front at Z = +2.4)]
    const laserGeo = new THREE.CylinderGeometry(0.025, 0.025, 12.0, 16);
    laserGeo.rotateX(Math.PI / 2);
    laserGeo.translate(0, 0, 6.0); // Offset forward
    const laserMat = new THREE.MeshBasicMaterial({
      color: 0xff1133,
      transparent: true,
      opacity: 0.9,
    });
    const laserBeam = new THREE.Mesh(laserGeo, laserMat);
    laserBeam.position.set(0, 0.08, 2.4);
    laserBeam.visible = false;
    pitchGroup.add(laserBeam);
    laserBeamRef.current = laserBeam;

    const laserGlow = new THREE.PointLight(0xff1133, 5.0, 12);
    laserGlow.position.set(0, 0.08, 3.2);
    laserGlow.visible = false;
    pitchGroup.add(laserGlow);
    laserGlowRef.current = laserGlow;

    // Animation Loop
    let animationFrameId: number;
    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);

      // Pulse laser effect if firing
      if (laserBeamRef.current && laserBeamRef.current.visible) {
        const pulse = 0.8 + Math.sin(Date.now() * 0.04) * 0.2;
        (laserBeamRef.current.material as THREE.MeshBasicMaterial).opacity = pulse;
      }

      renderer.render(scene, camera);
    };
    animate();

    // Mouse Drag Orbit Controls
    const handleMouseDown = (e: MouseEvent) => {
      isDraggingRef.current = true;
      previousMousePosition.current = { x: e.clientX, y: e.clientY };
    };

    const handleMouseMove = (e: MouseEvent) => {
      if (!isDraggingRef.current) return;

      const deltaX = e.clientX - previousMousePosition.current.x;
      const deltaY = e.clientY - previousMousePosition.current.y;

      cameraAngle.current.theta -= deltaX * 0.008;
      cameraAngle.current.phi = Math.max(0.1, Math.min(Math.PI / 2.1, cameraAngle.current.phi - deltaY * 0.008));

      updateCameraPosition();
      previousMousePosition.current = { x: e.clientX, y: e.clientY };
    };

    const handleMouseUp = () => {
      isDraggingRef.current = false;
    };

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      cameraRadius.current = Math.max(3.5, Math.min(14.0, cameraRadius.current + e.deltaY * 0.005));
      updateCameraPosition();
    };

    const containerEl = containerRef.current;
    containerEl.addEventListener('mousedown', handleMouseDown);
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    containerEl.addEventListener('wheel', handleWheel, { passive: false });

    const handleResize = () => {
      if (!containerRef.current || !rendererRef.current || !cameraRef.current) return;
      const newW = containerRef.current.clientWidth;
      const newH = containerRef.current.clientHeight;
      cameraRef.current.aspect = newW / newH;
      cameraRef.current.updateProjectionMatrix();
      rendererRef.current.setSize(newW, newH);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animationFrameId);
      containerEl.removeEventListener('mousedown', handleMouseDown);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      containerEl.removeEventListener('wheel', handleWheel);
      window.removeEventListener('resize', handleResize);
      renderer.dispose();
    };
  }, []);

  // Update Gimbal Orientation based on Pitch / Yaw Props in Real-Time!
  useEffect(() => {
    if (yawGroupRef.current) {
      yawGroupRef.current.rotation.y = -THREE.MathUtils.degToRad(yaw);
    }

    if (pitchGroupRef.current) {
      pitchGroupRef.current.rotation.x = THREE.MathUtils.degToRad(pitch);
      if (roll) {
        pitchGroupRef.current.rotation.z = THREE.MathUtils.degToRad(roll);
      }
    }
  }, [pitch, yaw, roll]);

  // Update Laser Visibilities
  useEffect(() => {
    if (laserBeamRef.current) {
      laserBeamRef.current.visible = laserFiring;
    }
    if (laserGlowRef.current) {
      laserGlowRef.current.visible = laserFiring;
    }
  }, [laserFiring]);

  return (
    <div className="relative w-full h-full min-h-[260px] bg-gradient-to-b from-[#0a0f1d] to-[#040810] rounded-xl border border-amber-500/30 overflow-hidden flex flex-col shadow-xl">
      {/* 3D Canvas Mount Point */}
      <div ref={containerRef} className="w-full flex-1 cursor-grab active:cursor-grabbing" />

      {/* Futuristic 3D View Overlays */}
      <div className="absolute top-2 left-2 flex items-center gap-2 bg-black/70 backdrop-blur-md px-2.5 py-1 rounded border border-amber-500/40 text-[11px] font-mono tracking-wider text-amber-300">
        <Compass className="w-3.5 h-3.5 animate-spin text-amber-400" style={{ animationDuration: '8s' }} />
        <span>3D SARI GİMBAL [KAMERA EKSENİ 40cm × 10cm × 8cm]</span>
      </div>

      <div className="absolute top-2 right-2 flex items-center gap-1.5">
        <button
          onClick={resetCamera}
          title="Reset View Angle"
          className="p-1.5 bg-black/60 hover:bg-amber-950/80 border border-amber-500/30 rounded text-amber-400 hover:text-amber-200 transition-colors"
        >
          <RotateCw className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Laser & Orientation Readout Badge */}
      <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between pointer-events-none text-xs font-mono">
        <div className="flex gap-2 bg-black/70 backdrop-blur-sm px-2.5 py-1 rounded border border-amber-500/30">
          <span className="text-amber-300">
            PITCH: <b className="text-white">{pitch.toFixed(1)}°</b>
          </span>
          <span className="text-amber-300">
            YAW: <b className="text-white">{yaw.toFixed(1)}°</b>
          </span>
        </div>

        <div className="flex items-center gap-2">
          {laserArmed && (
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-widest border ${
                laserFiring
                  ? 'bg-red-950/90 text-red-400 border-red-500 animate-pulse'
                  : 'bg-amber-950/80 text-amber-300 border-amber-500'
              }`}
            >
              {laserFiring ? '🔥 LASER FIRING' : '⚡ LASER ARMED'}
            </span>
          )}
          {systemState && (
            <span className="px-2 py-0.5 rounded text-[10px] font-bold tracking-widest bg-amber-950/80 text-amber-300 border border-amber-500/40">
              {systemState}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
