'use client';

import { useRef, useEffect } from 'react';
import * as THREE from 'three';
import { KeyMoment } from '@/lib/api';
import styles from './Pitch3D.module.css';

interface Pitch3DProps {
    moment: KeyMoment;
    width?: number;
    height?: number;
}

const safeNum = (val: unknown, defaultVal: number): number => {
    if (val === null || val === undefined) return defaultVal;
    const num = Number(val);
    return isNaN(num) || !isFinite(num) ? defaultVal : num;
};

export default function Pitch3D({ moment, width = 500, height = 350 }: Pitch3DProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const rendererRef = useRef<THREE.WebGLRenderer | null>(null);

    useEffect(() => {
        if (!containerRef.current) return;

        // Clear previous renderer
        if (rendererRef.current) {
            containerRef.current.removeChild(rendererRef.current.domElement);
            rendererRef.current.dispose();
        }

        // Scene
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x87CEEB); // Sky blue

        // Camera - dramatic angle
        const camera = new THREE.PerspectiveCamera(35, width / height, 0.1, 1000);
        camera.position.set(50, 80, 120);
        camera.lookAt(80, 0, 34);

        // High-quality renderer
        const renderer = new THREE.WebGLRenderer({
            antialias: true,
            alpha: true
        });
        renderer.setSize(width, height);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); // High DPI
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        rendererRef.current = renderer;
        containerRef.current.appendChild(renderer.domElement);

        // Lighting - more dramatic
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        scene.add(ambientLight);

        const sunLight = new THREE.DirectionalLight(0xffffcc, 1);
        sunLight.position.set(80, 100, 50);
        sunLight.castShadow = true;
        sunLight.shadow.mapSize.width = 2048;
        sunLight.shadow.mapSize.height = 2048;
        sunLight.shadow.camera.near = 0.5;
        sunLight.shadow.camera.far = 500;
        scene.add(sunLight);

        // Grass with stripes
        const grassCanvas = document.createElement('canvas');
        grassCanvas.width = 512;
        grassCanvas.height = 512;
        const ctx = grassCanvas.getContext('2d')!;

        // Draw stripes
        for (let i = 0; i < 16; i++) {
            ctx.fillStyle = i % 2 === 0 ? '#2d8c3c' : '#35a045';
            ctx.fillRect(0, i * 32, 512, 32);
        }

        const grassTexture = new THREE.CanvasTexture(grassCanvas);
        grassTexture.wrapS = THREE.RepeatWrapping;
        grassTexture.wrapT = THREE.RepeatWrapping;
        grassTexture.repeat.set(8, 8);

        const pitchGeometry = new THREE.PlaneGeometry(105, 68);
        const pitchMaterial = new THREE.MeshStandardMaterial({
            map: grassTexture,
            side: THREE.DoubleSide,
            roughness: 0.8
        });
        const pitch = new THREE.Mesh(pitchGeometry, pitchMaterial);
        pitch.rotation.x = -Math.PI / 2;
        pitch.position.set(52.5, 0, 34);
        pitch.receiveShadow = true;
        scene.add(pitch);

        // White lines - thicker
        const lineMaterial = new THREE.MeshBasicMaterial({ color: 0xffffff });

        // Helper function for thick lines
        const createThickLine = (points: THREE.Vector3[], thickness: number = 0.3) => {
            for (let i = 0; i < points.length - 1; i++) {
                const start = points[i];
                const end = points[i + 1];
                const direction = new THREE.Vector3().subVectors(end, start);
                const length = direction.length();

                const geometry = new THREE.BoxGeometry(length, 0.1, thickness);
                const line = new THREE.Mesh(geometry, lineMaterial);

                const mid = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5);
                line.position.copy(mid);
                line.position.y = 0.05;

                line.lookAt(end.x, 0.05, end.z);
                scene.add(line);
            }
        };

        // Outline
        createThickLine([
            new THREE.Vector3(0, 0, 0),
            new THREE.Vector3(105, 0, 0)
        ], 0.4);
        createThickLine([
            new THREE.Vector3(105, 0, 0),
            new THREE.Vector3(105, 0, 68)
        ], 0.4);
        createThickLine([
            new THREE.Vector3(105, 0, 68),
            new THREE.Vector3(0, 0, 68)
        ], 0.4);
        createThickLine([
            new THREE.Vector3(0, 0, 68),
            new THREE.Vector3(0, 0, 0)
        ], 0.4);

        // Center line
        createThickLine([
            new THREE.Vector3(52.5, 0, 0),
            new THREE.Vector3(52.5, 0, 68)
        ], 0.3);

        // Center circle
        const circleGeometry = new THREE.RingGeometry(8.8, 9.5, 64);
        const circleMaterial = new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.DoubleSide });
        const circle = new THREE.Mesh(circleGeometry, circleMaterial);
        circle.rotation.x = -Math.PI / 2;
        circle.position.set(52.5, 0.05, 34);
        scene.add(circle);

        // Penalty box (right)
        const pbWidth = 16.5;
        const pbHeight = 40.32;
        createThickLine([
            new THREE.Vector3(105 - pbWidth, 0, 34 - pbHeight / 2),
            new THREE.Vector3(105 - pbWidth, 0, 34 + pbHeight / 2)
        ], 0.3);
        createThickLine([
            new THREE.Vector3(105 - pbWidth, 0, 34 - pbHeight / 2),
            new THREE.Vector3(105, 0, 34 - pbHeight / 2)
        ], 0.3);
        createThickLine([
            new THREE.Vector3(105 - pbWidth, 0, 34 + pbHeight / 2),
            new THREE.Vector3(105, 0, 34 + pbHeight / 2)
        ], 0.3);

        // Goal box (right)
        const gbWidth = 5.5;
        const gbHeight = 18.32;
        createThickLine([
            new THREE.Vector3(105 - gbWidth, 0, 34 - gbHeight / 2),
            new THREE.Vector3(105 - gbWidth, 0, 34 + gbHeight / 2)
        ], 0.25);
        createThickLine([
            new THREE.Vector3(105 - gbWidth, 0, 34 - gbHeight / 2),
            new THREE.Vector3(105, 0, 34 - gbHeight / 2)
        ], 0.25);
        createThickLine([
            new THREE.Vector3(105 - gbWidth, 0, 34 + gbHeight / 2),
            new THREE.Vector3(105, 0, 34 + gbHeight / 2)
        ], 0.25);

        // Goal - 3D net frame
        const goalMaterial = new THREE.MeshStandardMaterial({ color: 0xffffff, metalness: 0.3 });

        // Posts
        const postGeom = new THREE.CylinderGeometry(0.15, 0.15, 2.44, 16);
        const leftPost = new THREE.Mesh(postGeom, goalMaterial);
        leftPost.position.set(105.1, 1.22, 34 - 3.66);
        scene.add(leftPost);

        const rightPost = new THREE.Mesh(postGeom, goalMaterial);
        rightPost.position.set(105.1, 1.22, 34 + 3.66);
        scene.add(rightPost);

        // Crossbar
        const crossbarGeom = new THREE.CylinderGeometry(0.12, 0.12, 7.32, 16);
        const crossbar = new THREE.Mesh(crossbarGeom, goalMaterial);
        crossbar.rotation.x = Math.PI / 2;
        crossbar.position.set(105.1, 2.44, 34);
        scene.add(crossbar);

        // Markers
        const actualX = safeNum(moment.position?.x, 80);
        const actualY = safeNum(moment.position?.y, 34);
        const suggestX = safeNum(moment.suggestion?.target_position?.x || moment.suggestion?.target_x, actualX + 8);
        const suggestY = safeNum(moment.suggestion?.target_position?.y || moment.suggestion?.target_y, actualY);

        // Actual position (RED X mark - failed shot)
        const xGroup = new THREE.Group();
        const xMaterial = new THREE.MeshStandardMaterial({
            color: 0xdc2626,
            emissive: 0xb91c1c,
            emissiveIntensity: 0.4
        });
        // X bar 1
        const xBar1Geom = new THREE.BoxGeometry(5, 1.2, 1.2);
        const xBar1 = new THREE.Mesh(xBar1Geom, xMaterial);
        xBar1.rotation.y = Math.PI / 4;
        xGroup.add(xBar1);
        // X bar 2
        const xBar2Geom = new THREE.BoxGeometry(5, 1.2, 1.2);
        const xBar2 = new THREE.Mesh(xBar2Geom, xMaterial);
        xBar2.rotation.y = -Math.PI / 4;
        xGroup.add(xBar2);
        xGroup.position.set(actualX, 2, actualY);
        xGroup.castShadow = true;
        scene.add(xGroup);

        // Suggested position (GREEN O ring - AI suggestion)
        const ringGeometry = new THREE.TorusGeometry(2.5, 0.8, 16, 32);
        const ringMaterial = new THREE.MeshStandardMaterial({
            color: 0x16a34a,
            emissive: 0x15803d,
            emissiveIntensity: 0.4
        });
        const ringMarker = new THREE.Mesh(ringGeometry, ringMaterial);
        ringMarker.rotation.x = -Math.PI / 2;
        ringMarker.position.set(suggestX, 2, suggestY);
        ringMarker.castShadow = true;
        scene.add(ringMarker);

        // Relocation trail
        const curve = new THREE.QuadraticBezierCurve3(
            new THREE.Vector3(actualX, 4, actualY),
            new THREE.Vector3((actualX + suggestX) / 2, 12, (actualY + suggestY) / 2),
            new THREE.Vector3(suggestX, 4, suggestY)
        );
        const trailMaterial = new THREE.MeshStandardMaterial({
            color: 0xf59e0b,
            emissive: 0xb45309,
            emissiveIntensity: 0.25,
            transparent: true,
            opacity: 0.9
        });
        const trailGeometry = new THREE.SphereGeometry(0.8, 18, 18);
        const trailPoints = curve.getPoints(6);
        trailPoints.slice(1, -1).forEach((point, idx) => {
            const marker = new THREE.Mesh(trailGeometry, trailMaterial);
            marker.position.set(point.x, 1.6 + idx * 0.12, point.z);
            marker.castShadow = true;
            scene.add(marker);
        });

        // Render
        renderer.render(scene, camera);

        // Cleanup
        return () => {
            if (containerRef.current && rendererRef.current) {
                containerRef.current.removeChild(rendererRef.current.domElement);
            }
            renderer.dispose();
        };
    }, [moment, width, height]);

    return (
        <div
            ref={containerRef}
            className={styles.pitch3d}
            style={{ width, height }}
        />
    );
}
