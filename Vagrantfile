# -*- mode: ruby -*-
# vi: set ft=ruby :
#
# TP RCSF - LEACH sous NS3 : VM Ubuntu 22.04 ARM64 pour Mac Apple Silicon (M1 à M4).
# Provider : QEMU (accélération Apple Hypervisor.framework, gratuit).
#
# PRÉPARATION (une seule fois, sur le Mac) :
#   brew install qemu
#   brew tap hashicorp/tap && brew install hashicorp/tap/hashicorp-vagrant
#   vagrant plugin install vagrant-qemu
#
# LANCEMENT (depuis ce dossier) :
#   vagrant up --provider=qemu        # 1re fois : 15 à 40 min (installe et compile NS3)
#   vagrant ssh
#
# Tout est décrit dans GUIDE.md.
#
# Réglages possibles sans modifier le fichier :
#   VM_MEMORY=6G VM_CPUS=4 vagrant up --provider=qemu
#   NS3_MODULES="" vagrant provision      # compiler TOUS les modules NS3 (≈ 1 h)

NS3_VERSION = ENV.fetch("NS3_VERSION", "3.40")
NS3_MODULES = ENV.fetch("NS3_MODULES", "core;network;mobility")
VM_MEMORY   = ENV.fetch("VM_MEMORY", "4G")
VM_CPUS     = ENV.fetch("VM_CPUS", "2").to_i

Vagrant.configure("2") do |config|
  config.vm.box = "perk/ubuntu-2204-arm64"
  config.vm.hostname = "rcsf-ns3"
  config.vm.boot_timeout = 600

  # Pas de dossier synchronisé (fragile avec QEMU) : les fichiers du TP sont copiés dans la VM
  # par le provisioning ci-dessous ; pour échanger ensuite avec le Mac, on utilise scp (voir GUIDE.md).
  config.vm.synced_folder ".", "/vagrant", disabled: true

  config.vm.provider "qemu" do |qe|
    qe.memory   = VM_MEMORY
    qe.smp      = VM_CPUS
    qe.ssh_port = "50022"      # changer si ce port est déjà utilisé sur le Mac
    # qe.qemu_dir = "/opt/homebrew/share/qemu"   # à décommenter si QEMU/firmware introuvable
  end

  # 1) Paquets système + swap (root)
  config.vm.provision "shell", name: "paquets", inline: <<-SHELL
    set -e
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y g++ gcc cmake ninja-build make git wget curl bzip2 rsync \
      python3 python3-pip python3-numpy python3-pandas python3-matplotlib \
      pkg-config sqlite3 libsqlite3-dev tmux htop
    if [ ! -f /swapfile ]; then
      fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
      echo '/swapfile none swap sw 0 0' >> /etc/fstab
    fi
  SHELL

  # 2) Copie des fichiers du TP (leach.cc, scripts) dans ~/tp_rcsf de la VM
  config.vm.provision "file", source: "tp_rcsf/", destination: "/home/vagrant/tp_rcsf"

  # 3) Installation et compilation de NS3, puis test de leach.cc (utilisateur vagrant)
  config.vm.provision "shell", name: "ns3", privileged: false,
    env: { "NS3_VERSION" => NS3_VERSION, "NS3_MODULES" => NS3_MODULES },
    inline: <<-SHELL
    set -e
    mkdir -p "$HOME/tp_rcsf/results" "$HOME/tp_rcsf/figures" "$HOME/tp_rcsf/rapport"
    chmod +x "$HOME/tp_rcsf/scripts/"*.sh "$HOME/tp_rcsf/scripts/"*.py
    bash "$HOME/tp_rcsf/scripts/install_ns3.sh"
  SHELL

  config.vm.post_up_message = <<-MSG
    VM prête.  vagrant ssh  puis :
      bash ~/tp_rcsf/scripts/run_all.sh        # lance toutes les expériences (5 graines)
      python3 ~/tp_rcsf/scripts/plot_results.py  # courbes + tableaux dans ~/tp_rcsf/figures
    Récupérer les figures sur le Mac (depuis ce dossier) :
      vagrant ssh-config > ssh.cfg && scp -F ssh.cfg -r default:~/tp_rcsf/figures ./figures
  MSG
end
