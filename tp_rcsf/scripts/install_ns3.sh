#!/usr/bin/env bash
# Installe NS3 (profil optimisé) dans ~/ns3 et compile les modules nécessaires au TP.
# Utilisé automatiquement par le Vagrantfile ; relançable à la main : bash ~/tp_rcsf/scripts/install_ns3.sh
set -euo pipefail
NS3_VERSION="${NS3_VERSION:-3.40}"
# Modules minimaux pour leach.cc (compilation rapide). Pour tout compiler : NS3_MODULES="" (≈ 1 h)
NS3_MODULES="${NS3_MODULES-core;network;mobility}"
MARK="$HOME/.ns3_ready_${NS3_VERSION}"

if [ -f "$MARK" ] && [ -d "$HOME/ns3" ]; then
  echo "NS3 $NS3_VERSION déjà installé."
  exit 0
fi

echo ">>> Espace disque disponible :"; df -h / | tail -n 1
cd "$HOME"

if [ ! -d "$HOME/ns-$NS3_VERSION" ]; then
  echo ">>> Récupération de NS3 $NS3_VERSION"
  if git clone --depth 1 --branch "ns-$NS3_VERSION" https://github.com/nsnam/ns-3-dev-git.git "ns-$NS3_VERSION" 2>/dev/null; then
    echo "    (depuis GitHub)"
  elif wget -q --show-progress "https://www.nsnam.org/releases/ns-allinone-$NS3_VERSION.tar.bz2" -O ns3.tar.bz2; then
    tar xjf ns3.tar.bz2 && mv "ns-allinone-$NS3_VERSION/ns-$NS3_VERSION" "$HOME/ns-$NS3_VERSION" && rm -rf "ns-allinone-$NS3_VERSION" ns3.tar.bz2
    echo "    (depuis nsnam.org)"
  else
    rm -rf "ns-$NS3_VERSION"
    git clone --depth 1 --branch "ns-$NS3_VERSION" https://gitlab.com/nsnam/ns-3-dev.git "ns-$NS3_VERSION"
    echo "    (depuis GitLab)"
  fi
fi

ln -sfn "$HOME/ns-$NS3_VERSION" "$HOME/ns3"
cd "$HOME/ns3"
mkdir -p results

echo ">>> Configuration (profil optimisé)"
if [ -n "$NS3_MODULES" ]; then
  ./ns3 configure --build-profile=optimized --enable-modules="$NS3_MODULES" --disable-examples --disable-tests
else
  ./ns3 configure --build-profile=optimized --enable-examples --disable-tests
fi

echo ">>> Compilation de NS3 (première fois : quelques minutes à 1 h selon les modules)"
./ns3 build -j "$(nproc)"

# Copie de leach.cc dans scratch/ et test rapide (5 rounds)
if [ -f "$HOME/tp_rcsf/leach.cc" ]; then
  cp "$HOME/tp_rcsf/leach.cc" "$HOME/ns3/scratch/leach.cc"
  ./ns3 build scratch/leach
  mkdir -p "$HOME/tp_rcsf/results"
  echo ">>> Test rapide de leach (5 rounds)"
  ./ns3 run --no-build "scratch/leach --n=20 --rounds=5 --out=/tmp/leach_test.csv"
  head -n 3 /tmp/leach_test.csv
fi

touch "$MARK"
echo ">>> NS3 $NS3_VERSION prêt dans ~/ns3"
