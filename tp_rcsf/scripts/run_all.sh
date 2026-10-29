#!/usr/bin/env bash
# Lance toutes les expériences du TP (LEACH sous NS3) et écrit les CSV dans ~/tp_rcsf/results.
# Usage : bash ~/tp_rcsf/scripts/run_all.sh [nombre_de_graines]   (défaut : 5)
set -euo pipefail
NS3_DIR="${NS3_DIR:-$HOME/ns3}"
RES="${RES:-$HOME/tp_rcsf/results}"
SEEDS="${1:-5}"
mkdir -p "$RES"

cp "$HOME/tp_rcsf/leach.cc" "$NS3_DIR/scratch/leach.cc"
cd "$NS3_DIR"
echo ">>> Compilation de scratch/leach"
./ns3 build scratch/leach

run() {   # run <n> <seed> <fichier> [options supplémentaires]
  local n=$1 s=$2 f=$3; shift 3
  ./ns3 run --no-build "scratch/leach --n=$n --run=$s --out=$RES/$f $*" | sed "s/^/[n=$n run=$s] /"
}

echo ">>> Expériences A et C : 100 nœuds, 1000 rounds, canal idéal"
for s in $(seq 1 "$SEEDS"); do run 100 "$s" "leach_n100_run$s.csv"; done

echo ">>> Expérience B : passage à l'échelle (50 et 300 nœuds)"
for n in 50 300; do
  for s in $(seq 1 "$SEEDS"); do run "$n" "$s" "leach_n${n}_run$s.csv"; done
done

echo ">>> Variante avec pertes aléatoires (2 %) pour le taux de livraison"
for s in $(seq 1 "$SEEDS"); do run 100 "$s" "leach_per_n100_run$s.csv" --per=0.02; done

echo ">>> Terminé. CSV dans $RES"
