# Experimental Studio Desktop: never change the existing Steam or XFCE Wolf profiles.
# Wolf's upstream XFCE image is Ubuntu 25.04 (EOL since Jan 2026).
# Build and test privately only; a maintained base is required before production hardening.
FROM ghcr.io/games-on-whales/xfce@sha256:a0955349089f41000dad72d86bc1372871948be37abfdbe9df3558a029bae724

LABEL org.opencontainers.image.title="OptiPlex Studio Desktop (experimental)"
LABEL org.opencontainers.image.description="Isolated Wolf XFCE desktop for Godot and Krita; no changes to existing gaming profile"

# System-wide Flatpaks are baked into this image, avoiding fragile stateful installs
# in Wolf's disposable session container. The build result is versioned by image ID.
RUN flatpak remote-add --system --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo \
 && flatpak install --system --noninteractive --assumeyes flathub org.godotengine.Godot org.kde.krita \
 && flatpak override --system --filesystem=/projects org.godotengine.Godot \
 && flatpak override --system --filesystem=/projects org.kde.krita \
 && echo '=== PIN THIS IMAGE DIGEST AFTER BUILD ===' \
 && flatpak info --system org.godotengine.Godot \
 && flatpak info --system org.kde.krita

# Image entrypoint and existing GOW startup scripts remain unchanged.
# The separately configured Studio Wolf app will mount only /projects read/write.
