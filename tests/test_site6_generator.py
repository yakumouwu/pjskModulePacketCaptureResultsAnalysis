#!/usr/bin/env python3
"""
Site 6 Map Test Generator
Generate test images with different parameters for map calibration
"""
import os
import subprocess
import sys
from pathlib import Path

def main():
    # Paths
    project_root = Path(__file__).parent
    json_path = "02_captures/decoded_api/mysekai/mysekai_real_4maps_id12.json"
    assets_dir = "04_artifacts/docker_receiver_3939_dev/dockerScripts/mysekai_assets"
    script_path = "04_artifacts/docker_receiver_3939_dev/dockerScripts/render_mysekai_map.py"
    output_dir = "02_captures/decoded_api/mysekai/maps"

    # Test configurations
    test_configs = [
        {
            "name": "default",
            "env": {},
            "output": f"{output_dir}/site6_test_default.png"
        },
        {
            "name": "half_z_50",
            "env": {"SITE6_WORLD_HALF_Z": "50.0"},
            "output": f"{output_dir}/site6_test_half_z_50.png"
        },
        {
            "name": "half_z_80",
            "env": {"SITE6_WORLD_HALF_Z": "80.0"},
            "output": f"{output_dir}/site6_test_half_z_80.png"
        },
        {
            "name": "scale_z_delta_1.0",
            "env": {"SITE6_SCALE_Z_DELTA": "1.0"},
            "output": f"{output_dir}/site6_test_scale_z_delta_1.0.png"
        },
        {
            "name": "scale_z_delta_2.0",
            "env": {"SITE6_SCALE_Z_DELTA": "2.0"},
            "output": f"{output_dir}/site6_test_scale_z_delta_2.0.png"
        },
        {
            "name": "offset_z_delta_10",
            "env": {"SITE6_OFFSET_Z_DELTA": "10.0"},
            "output": f"{output_dir}/site6_test_offset_z_delta_10.png"
        },
        {
            "name": "offset_z_delta_minus10",
            "env": {"SITE6_OFFSET_Z_DELTA": "-10.0"},
            "output": f"{output_dir}/site6_test_offset_z_delta_minus10.png"
        },
        {
            "name": "combined_small",
            "env": {
                "SITE6_WORLD_HALF_Z": "50.0",
                "SITE6_SCALE_Z_DELTA": "0.5"
            },
            "output": f"{output_dir}/site6_test_combined_small.png"
        }
    ]

    print("Site 6 Map Test Generator")
    print("=" * 50)

    success_count = 0
    fail_count = 0

    for config in test_configs:
        print(f"\nGenerating: {config['name']}")
        print(f"Output: {config['output']}")
        print(f"Environment: {config['env']}")

        try:
            # Build command
            cmd = [
                sys.executable,
                script_path,
                json_path,
                config['output'],
                assets_dir,
                "--site-id", "6",
                "--target-size", "1024"
            ]

            # Set environment variables
            env = os.environ.copy()
            env.update(config['env'])

            # Run command
            result = subprocess.run(
                cmd,
                env=env,
                cwd=project_root,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                print(f"✅ Success: {config['name']}")
                success_count += 1
            else:
                print(f"❌ Failed: {config['name']}")
                print(f"Error: {result.stderr}")
                fail_count += 1

        except Exception as e:
            print(f"❌ Exception: {config['name']}")
            print(f"Error: {str(e)}")
            fail_count += 1

    print("\n" + "=" * 50)
    print(f"Summary: {success_count} success, {fail_count} failed")

    if fail_count == 0:
        print("\n✅ All test images generated successfully!")
        print(f"Output directory: {output_dir}/")
        return 0
    else:
        print(f"\n⚠️ {fail_count} test image(s) failed to generate")
        return 1

if __name__ == "__main__":
    sys.exit(main())