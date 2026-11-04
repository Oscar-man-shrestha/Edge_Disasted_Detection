# Edge pipeline image for Jetson Nano (JetPack 4.6, L4T r32.7).
# Build once on the board:  sudo docker build -t edge-drone jetson/
FROM ultralytics/ultralytics:latest-jetson-jetpack4

# Set to 1 only if the fire model (YOLO26) fails to load with the bundled Ultralytics:
#   sudo docker build --build-arg UPGRADE_ULTRALYTICS=1 -t edge-drone jetson/
# --no-deps keeps the image's CUDA-enabled torch untouched.
ARG UPGRADE_ULTRALYTICS=0
RUN if [ "$UPGRADE_ULTRALYTICS" = "1" ]; then pip install --no-cache-dir --no-deps -U ultralytics; fi

RUN pip install --no-cache-dir flask requests pyserial \
 && (pip install --no-cache-dir pymavlink || echo "pymavlink not installed (only needed for EDGE_GPS=mavlink)")

WORKDIR /work
CMD ["bash"]
