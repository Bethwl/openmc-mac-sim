@echo off
set SCRIPT=%1
shift
wsl -d Ubuntu-24.04 bash -c "export PATH=/home/ht/miniconda3/envs/openmc/bin:$PATH && export OPENMC_CROSS_SECTIONS=/home/ht/nuclear_data/endfb-viii.0-hdf5/endfb-viii.0-hdf5/cross_sections.xml && cd /mnt/c/2026.9.28_Paper10/Openmc_mac && python %SCRIPT% %1 %2 %3 %4 %5"
