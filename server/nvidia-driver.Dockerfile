# NOW Host NVIDIA driver userspace image.
# Adapted from Games on Whales (MIT), images/nvidia-driver/Dockerfile:
# https://github.com/games-on-whales/gow/blob/a1fbf9af2babfe2065d3af55e30ecf0bcb2dcd63/images/nvidia-driver/Dockerfile
# Require SHA256 of official NVIDIA .run file before executing it.
# Does not install drivers or load kernel modules on the host.
FROM ubuntu:22.04 AS nvidia-installer

ARG NV_VERSION
ARG NV_SHA256
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends curl ca-certificates kmod pkg-config libglvnd-dev vulkan-tools && \
    curl -fsSLo /tmp/nvidia-installer.run \
      "https://download.nvidia.com/XFree86/Linux-x86_64/$NV_VERSION/NVIDIA-Linux-x86_64-$NV_VERSION.run" && \
    echo "$NV_SHA256  /tmp/nvidia-installer.run" | sha256sum --check --status && \
    chmod 0700 /tmp/nvidia-installer.run && \
    mkdir -p /usr/nvidia && \
    /tmp/nvidia-installer.run --silent -z --skip-depmod --skip-module-unload \
      --no-nvidia-modprobe --no-kernel-modules --no-kernel-module-source \
      --opengl-prefix=/usr/nvidia --wine-prefix=/usr/nvidia \
      --utility-prefix=/usr/nvidia --utility-libdir=lib \
      --compat32-prefix=/usr/nvidia --compat32-libdir=lib32 \
      --egl-external-platform-config-path=/usr/nvidia/share/egl/egl_external_platform.d \
      --glvnd-egl-config-path=/usr/nvidia/share/glvnd/egl_vendor.d \
      --no-distro-scripts && \
    rm -f /tmp/nvidia-installer.run

RUN printf '/usr/nvidia/lib\n/usr/nvidia/lib32\n' > /etc/ld.so.conf.d/nvidia.conf && ldconfig

FROM scratch
COPY --from=nvidia-installer /usr/nvidia/ /usr/nvidia/
COPY --from=nvidia-installer /etc/vulkan/icd.d/nvidia_icd.json /usr/nvidia/share/vulkan/icd.d/
COPY --from=nvidia-installer /bin/sh /bin/sh
