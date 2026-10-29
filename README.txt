TP RCSF - LEACH sous NS3 - Mac Apple Silicon
1) brew install qemu ; brew tap hashicorp/tap && brew install hashicorp/tap/hashicorp-vagrant ; vagrant plugin install vagrant-qemu
2) vagrant up --provider=qemu      (15 à 40 min la première fois)
3) vagrant ssh
4) bash ~/tp_rcsf/scripts/run_all.sh && python3 ~/tp_rcsf/scripts/plot_results.py
Tout est détaillé dans GUIDE_TP_RCSF.pdf
