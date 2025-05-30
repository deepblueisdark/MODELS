#!/bin/bash

#-------------------------------------------------------------------------------
#
#       WRF AND MPAS MODEL INSTALLER
#
#       INSTALLS ALL LIBRARIES REQUIRED TO BUILD THE WRF AND MPAS MODELS.
#       EVERYTHING IS USER-DEFINED AND MODIFIABLE.
#
#       REGINALDO VENTURA DE SA - RVS - (reginaldo.venturadesa@gmail.com)
#       20/03/2025 : WRF
#       15/04/2025 : MPAS
# ------------------------------------------------------------
#
#  29/05 -  python 3 tests and  gfortran version tests  (RVS)
#
#-------------------------------------------------------------------------------

# ============================
# SCRIPT DOCUMENTATION HEADER
# ============================
#
# This script automates the installation of all dependencies required to build the
# WRF (Weather Research and Forecasting) and MPAS (Model for Prediction Across Scales) models.
# It supports different compilers (GNU, Intel, NVIDIA) and MPI configurations.
#
# Key Features:
# - Modular execution using the OPTIONS array
# - Automatic system update and package installation
# - Automated download, extraction, compilation, and installation of dependencies
# - Parallel build based on CPU detection
# - Environment variable setup for compilers and library paths
# - Compatibility with RedHat, Ubuntu, and Debian-based systems
#
# Usage Instructions:
# -------------------
# 1. Set the desired COMPILER (e.g., GNU, INTEL, NVIDIA) and MPI (e.g., MPICH, INTEL_MPI).
# 2. Enable the desired installation steps by setting the respective index in the OPTIONS array to 1.
# 3. Run the script:
#
#        bash wrf_mpas_installer.sh
#
# Notes:
# - PROMPTOK=1 will pause the script after each installation step for user confirmation.
# - Use this script in a clean environment or virtual machine for best results.
#
# Maintainer: Reginaldo Ventura de Sá
# License: MIT or Public Domain (user-defined)
#
# ==============================
# END OF DOCUMENTATION HEADER
# ==============================

# ==============================
# COMMANDS TO EXECUTE INSTALLER
# ==============================
#
# Enable each step below by setting the corresponding OPTIONS entry to 1
# Example: OPTIONS[0]=1 will enable system update
#
# OPTIONS=(
#   1  # [0] Update system packages
#   1  # [1] Create directories
#   1  # [2] Download necessary files
#   1  # [3] Install MPICH
#   1  # [4] Install ZLIB
#   1  # [5] Install LIBPNG
#   1  # [6] Install JASPER
#   1  # [7] Install HDF5
#   1  # [8] Install PNETCDF
#   1  # [9] Install NETCDF-C
#   1  # [10] Install NETCDF-FORTRAN
#   1  # [11] Install PIO (MPAS)
#   1  # [12] Compile WRF
#   1  # [13] Compile WPS
#   1  # [14] Compile MPAS
#   1  # [15] Install OPENJPEG
#   1  # [16] Install AEC
#   1  # [17] Install ECCODES
# )
#
# Execute the script with:
# bash wrf_mpas_installer.sh
#
# ============================
# END OF COMMANDS SECTION
# ============================

# All actual installation and setup code continues below this block.
# The rest of the original code is preserved.

# -----------------------------------------------------------------------
#
#            COMPILER (default: gnu) 
#
#
# Use default COMPILER if not defined by user
#COMPILER=
COMPILER=${COMPILER:-GNU}

#---------------------------------------------------------------------------
#
#        INSTALL LOCAL 
#
#
HOME_DIR=$HOME
INSTALLATION_PATH="$HOME_DIR/MODELS"
export INSTALL_DIR="$INSTALLATION_PATH/$COMPILER/"


#------------------------------------------------------------------------------
#
# Define download directory
#
#
#
export DOWNLOADS="$HOME/Downloads"



#-----------------------------------------------------------------------------------
#
#
#
#    se  MPI não for definido ou vazio padrão "$INSTALLATION_PATH/$COMPILER/ 
#    se MPI=MPICH  tudo sera instalado em "$INSTALLATION_PATH/$COMPILER/MPICH"
#    se MPI=INTEL_MPI  tyudo sera instaaldo em "$INSTALLATION_PATH/$COMPILER/INTEL_MPI/"
#    se MPI= qualquer coisa ,  tudo sera instalado em "$INSTALLATION_PATH/$COMPILER/qualquer coisa"
#
#export MPI=




if [ "$MPI" == "MPICH" ]; then
    export INSTALL_DIR="$INSTALLATION_PATH/$COMPILER/MPICH"
    export LIBS_DIR=$INSTALL_DIR/
    export MPI_DIR=$LIBS_DIR/

elif [ "$MPI" == "INTEL_MPI" ]; then
    export INSTALL_DIR="$INSTALLATION_PATH/$COMPILER/INTEL_MPI/"
    export LIBS_DIR=$INSTALL_DIR
    #export MPI_DIR=$INSTALL_DIR     

elif [ -n "$MPI" ]; then
    export INSTALL_DIR="$INSTALLATION_PATH/$COMPILER/$MPI/"
    export LIBS_DIR=$INSTALL_DIR/  # qualquer valor customizado definido em MPI
	export MPI_DIR=$LIBS_DIR
else
	export INSTALL_DIR="$INSTALLATION_PATH/$COMPILER/"
    export LIBS_DIR=$INSTALL_DIR    #padrão 
	export MPI_DIR=$LIBS_DIR
fi


#-----------------------------------------------------------------------------
#
#
# SE PARALLEL VERISON FOR = 1  TODAS AS BIBLIOTECAS SÃO COMPILAS COM MPI   
#  OU SEJA , CC=mpicc  E NAÕ CC=gcc (GNU)
#            CC=mpiicc E NÃO CC=icc  (intel)  
# 
#
PARALLEL_VERSION=0  



#---------------------------------------------------------------------------------------
#
# Flag to start a clean installation from scratch
# Warning: this will delete the entire installation directory!
#
# Set INSTALL_FROM_SCRATCH=1 to enable
#
# INSTALL_FROM_SCRATCH=0
# if [ "$INSTALL_FROM_SCRATCH" -eq 1 ]; then
#     rm -rf "$INSTALL_DIR"
#     read -p "Are you sure? Press ENTER to continue or CTRL+C to cancel. "
#     echo "Installation will start from scratch."
# fi

#---------------------------------------------------------------------------
#
# PROMPTOK=1 means the script will pause after each installation step
#
#----------------------------------------------------------------------------
PROMPTOK=1

#-----------------------------------------------------------------------------
#
#                        OPTIONS
#
# Each entry in the OPTIONS array corresponds to a specific step.
# If set to 1, that step will be executed; if 0, it will be skipped.
#
OPTIONS=(
    1  #### [0]  Update system packages       WRF/MPAS/ICON
    1  #### [1]  Create directories           WRF/MPAS/ICON 
    1  #### [2]  Download necessary files     WRF/MPAS/ICON
    1  #### [3]  MPICH                        WRF/MPAS/ICON 
    1  #### [4]  ZLIB (serial)                WRF/MPAS/ICON
    1  #### [5]  libpng                       WRF/MPAS/ICON
    1  #### [6]  jasper                       WRF/MPAS/ICON
    1  #### [7]  HDF5 (serial)                WRF/MPAS/ICON
    1  #### [8]  Parallel NetCDF              WRF/MPAS/ 
    1  #### [9]  NetCDF-C                     WRF/MPAS/ICON 
    1  #### [10] NetCDF-Fortran               WRF/MPAS/ICON
	1  #### [11] PIO                          MPAS
    1  #### [12] Latest WRF version           WRF
    1  #### [13] Latest WPS                   WRF/MPAS
	0  #### [14] MPAS                         MPAS 

   )
#-------------------------------------------------------------------------------


#-----------------------------------------------------------------------------
#
#   Library versions   
#
#
# ----------------------------------------------------------------------------
#


export HDF5_Version="1_14_2"
export Zlib_Version="1.3.1"
export Netcdf_C_Version="4.9.2"
export Netcdf_Fortran_Version="4.6.1"
export Mpich_Version="4.2.1"
export Libpng_Version="1.6.39"
export Jasper_Version="1.900.1"
export Pnetcdf_Version="1.12.3"
export Pio_Version="2_5_9"
export jpeg_version="2.5.3"
export ecc_version=2.41.0

#--------------------------------------------------------------------------
#
#
#                       LIB PATHS 
#
#
#---------------------------------------------------------------------------

# Base paths for core scientific libraries (all installed under $LIBS_DIR)
export NETCDF=$LIBS_DIR            # NetCDF (C and Fortran)
export HDF5=$LIBS_DIR              # HDF5
export HDF5_DIR=$LIBS_DIR              # HDF5
export PIO=$LIBS_DIR 
export PNETCDF=$LIBS_DIR           # Parallel NetCDF

# Specific paths for Jasper library (used for GRIB2 support in WRF)
export JASPERLIB=$LIBS_DIR/lib
export JASPERINC=$LIBS_DIR/include

export JPEG_LIBRARY=$LIBS_DIR/lib 
export JPEG_INCLUDE_DIR=$LIBS_DIR/include 

# Compiler flags for include and link paths
export CPPFLAGS="-I$LIBS_DIR/include"     # Include headers
export LDFLAGS="-L$LIBS_DIR/lib"          # Link libraries

# Runtime library path (ensures dynamic libraries are found at runtime)
export LD_LIBRARY_PATH=$LIBS_DIR/lib:$MPI_DIR/lib:$LD_LIBRARY_PATH

#=======================================
# MPI executable paths and wrappers
#=======================================

# Add MPI binary directory to PATH to ensure wrappers are available in the shell
export PATH=$MPI_DIR/bin:$PATH

# Standard MPI Fortran compiler wrappers (used by libraries and models like WRF)
export MPIFC=$MPI_DIR/bin/mpifort
export MPIF77=$MPI_DIR/bin/mpifort
export MPIF90=$MPI_DIR/bin/mpifort

# Standard MPI C compiler wrappers
export MPICC=$MPI_DIR/bin/mpicc
export MPICXX=$MPI_DIR/bin/mpicxx


#------------------------------------------------------------------
#
#                     CPU RESOURCE MANAGEMENT
#
#-------------------------------------------------------------------

#
#
# Set to true if you want to force the use of all available CPU cores
USE_ALL_CORES=false

#
#
# Detect total number of CPU cores available on the system
CPU_CORE=$(nproc)
echo "TOTAL AVAILABLE CPU CORES: $CPU_CORE"

#
#
# Threshold to define a low-core system (adjustable)
CPU_CORE_LIMIT=8

#
#
# Check if the user wants to use all cores
if [ "$USE_ALL_CORES" = true ]; then
  CPU_HALF_EVEN=$CPU_CORE
  echo "USING ALL AVAILABLE CORES AS CONFIGURED"
else
  # Calculate half the cores and ensure it's an even number
  CPU_HALF=$((CPU_CORE / 2))
  CPU_HALF_EVEN=$((CPU_HALF - (CPU_HALF % 2)))

  # If system has few cores (≤ 12), force only 2 cores to be used
  if [ $CPU_CORE -le $CPU_CORE_LIMIT ]; then
    CPU_HALF_EVEN=2
    echo "LOW-CORE SYSTEM DETECTED – FORCING USAGE OF 2 CORES ONLY"
  fi
fi

#
#
# Export the final value to be used in parallel commands (e.g., make -j$CPU_HALF_EVEN)
#
export CPU_HALF_EVEN
echo "CORES TO BE USED BY THE SCRIPT: $CPU_HALF_EVEN"





#------------------------------------------------------------------------------
#
# Compiler configuration based on the COMPILER variable
#
#



if [ "$COMPILER" == "GNU" ]; then
    export CC=gcc
    export CXX=g++
    export FC=gfortran

    export CFLAGS="-O3 -fPIC -Wno-implicit-function-declaration -Wno-incompatible-function-pointer-types"
    export CXXFLAGS="-O3 -fPIC"
    export FFLAGS="-O3 -fPIC"
    export FCFLAGS="-O3 -Wno-implicit-function-declaration -Wno-incompatible-function-pointer-types -fPIC -fno-second-underscore -ffree-form   -Wno-implicit-function-declaration -Wno-incompatible-function-pointer-types"
    export LDFLAGS="-fPIC"


elif [ "$COMPILER" == "INTEL" ]; then
    # Detecta se é Intel clássico (ifort) ou Intel OneAPI (ifx)
    if command -v ifx &>/dev/null; then
        export CC=icx
        export CXX=icpx
        export FC=ifx
    else
        export CC=icc
        export CXX=icpc
        export FC=ifort
    fi

    export CFLAGS="-O2 -fPIC"
    export CXXFLAGS="-O2 -fPIC"
    export FFLAGS="-O2 -fPIC"
    export FCFLAGS="-O2 -fPIC -free"
    export LDFLAGS="-fPIC"

elif [ "$COMPILER" == "NVIDIA" ]; then
    export CC=nvc
    export CXX=nvc++
    export FC=nvfortran

    export CFLAGS="-O2 -fPIC"
    export CXXFLAGS="-O2 -fPIC"
    export FFLAGS="-O2 -fPIC"
    export FCFLAGS="-O2 -fPIC -Mfreeform"
    export LDFLAGS="-fPIC"

else
    echo "ERRO: Valor inválido para COMPILER. Use: GNU, INTEL ou NVIDIA."
    exit 1
fi


#-----------------------------------------------------------------------------
#
#
#   Test block to check if Python version is greater than or equal to 3
#
#
#-------------------------------------------------------------------------------
#
#
#
PYTHON_CMD=$(command -v python3 || command -v python)

if [ -z "$PYTHON_CMD" ]; then
    echo "Nenhuma versão do Python encontrada."
    exit 1
fi

PYTHON_VERSION=$("$PYTHON_CMD" -c 'import sys; print(sys.version_info[0])')

if [ "$PYTHON_VERSION" -ge 3 ]; then
    echo "$PYTHON_CMD é Python 3 ou superior."
else
    echo "$PYTHON_CMD é inferior à versão 3."
    exit 1
fi




#-------------------------------------------------------------------------------------
#
# Step [0] - Update system and install required development packages
#
# This step prepares the system by installing compilers, development tools,
# libraries and utilities required to build all dependencies and run the WRF model.
#
# The Linux distribution is detected automatically using /etc/os-release.
# Supported distributions:
#   - REDHAT-based (Rocky, AlmaLinux, CentOS, Fedora)
#   - UBUNTU
#   - DEBIAN
#

# Detect system distribution
if [ -f /etc/os-release ]; then
    DISTRO_ID=$(awk -F= '/^ID=/{gsub(/"/, "", $2); print $2}' /etc/os-release)
else
    echo "ERROR: Cannot determine Linux distribution. '/etc/os-release' not found."
    exit 1
fi

if [ "${OPTIONS[0]}" -eq 1 ]; then
    echo ">>> [0] Detected system: $DISTRO_ID"
    echo ">>> Updating system and installing required packages..."

    #
    # --------------------------
    # Red Hat-based systems
    # --------------------------
    #
    if [[ "$DISTRO_ID" == "rhel" || "$DISTRO_ID" == "rocky" || "$DISTRO_ID" == "fedora" || "$DISTRO_ID" == "centos" ]]; then
        sudo dnf update -y
        sudo dnf upgrade -y

        # Compilers and core development tools
        sudo dnf install -y gcc gcc-gfortran gcc-c++ libtool \
                            automake autoconf make m4 cmake patch curl tar unzip wget

        # Java (some tools like Jasper or viewers may require it)
        sudo dnf install -y java-1.8.0-openjdk java-1.8.0-openjdk-devel

        # Shells and useful utilities
        sudo dnf install -y csh ksh tcsh time git bash-completion wget git

        # Core libraries for building dependencies
        sudo dnf install -y zlib zlib-devel libpng libpng-devel jasper jasper-devel \
                            hdf5 hdf5-devel netcdf netcdf-fortran

        # Visualization tools and required X11 components
        sudo dnf install -y ncview ncl \
                            libX11-devel libXaw-devel libXmu-devel libXt-devel

        # Full development environment (equivalent to build-essential)
        sudo dnf groupinstall -y "Development Tools"

    #
    # --------------------------
    # Ubuntu systems
    # --------------------------
    #
    elif [[ "$DISTRO_ID" == "ubuntu" ]]; then
        sudo apt update -y
        sudo apt upgrade -y

        # Compilers and core development tools
        sudo apt install -y build-essential gfortran g++ libtool \
                            automake autoconf make m4 cmake patch curl tar unzip wget

        # Java
        sudo apt install -y openjdk-8-jdk

        # Shells and utilities
        sudo apt install -y csh ksh tcsh time git bash-completion wget git 

        # Libraries
        sudo apt install -y zlib1g-dev libpng-dev libjasper-dev \
                            libhdf5-serial-dev libnetcdf-dev libnetcdff-dev

        # Visualization and X11 support
        sudo apt install -y ncview ncl-ncarg \
                            libx11-dev libxaw7-dev libxmu-dev libxt-dev

    #
    # --------------------------
    # Debian systems
    # --------------------------
    #
    elif [[ "$DISTRO_ID" == "debian" ]]; then
        sudo apt update -y
        sudo apt upgrade -y

        # Compilers and core development tools
        sudo apt install -y build-essential gfortran g++ libtool \
                            automake autoconf make m4 cmake patch curl tar unzip wget

        # Java
        sudo apt install -y default-jdk

        # Shells and utilities
        sudo apt install -y csh ksh tcsh time git bash-completion wget git 

        # Libraries
        sudo apt install -y zlib1g-dev libpng-dev libjasper-dev \
                            libhdf5-dev libnetcdf-dev libnetcdff-dev

        # Visualization and X11 support
        sudo apt install -y ncview ncl-ncarg \
                            libx11-dev libxaw7-dev libxmu-dev libxt-dev

    #
    # --------------------------
    # Unsupported or unknown
    # --------------------------
    #
    else
        echo "ERROR: Unsupported or unknown Linux distribution: '$DISTRO_ID'"
        exit 1
    fi

    #
    # Pause if PROMPTOK is enabled
    #
    if [ "$PROMPTOK" -eq 1 ]; then
        read -p "System update complete. Press ENTER to continue..."
    fi
fi






#-----------------------------------------------------------------------------
#
# Step [1] - Create working directories
#
if [ "${OPTIONS[1]}" -eq 1 ]; then
    echo ">>> [1] Creating working directories..."
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$LIBS_DIR"
    mkdir -p "$DOWNLOADS"
	mkdir -p "$MPI_DIR"
    if [ "$PROMPTOK" -eq 1 ]; then read -p "Press ENTER to continue..."; fi
fi



#--------------------------------------------------------------------------------
#
# Step [2] - Download all libraries in a single session
#



if [ "${OPTIONS[2]}" -eq 1 ]; then

    echo ">>> [2] Downloading all required libraries..."
    
    # Go to the download directory
    cd "$DOWNLOADS"

    #
    # ZLIB
    #
    wget -nc https://www.zlib.net/zlib-$Zlib_Version.tar.gz

    #
    # MPICH
    #
    wget -nc https://www.mpich.org/static/downloads/$Mpich_Version/mpich-$Mpich_Version.tar.gz

    #
    # LIBPNG
    #
    wget -nc https://download.sourceforge.net/libpng/libpng-$Libpng_Version.tar.gz

    #
    # JASPER
    #
    wget -nc https://www.ece.uvic.ca/~frodo/jasper/software/jasper-$Jasper_Version.zip

    #
    # HDF5
    #
    wget -nc https://github.com/HDFGroup/hdf5/archive/refs/tags/hdf5-$HDF5_Version.tar.gz
    # Example: https://github.com/HDFGroup/hdf5/archive/refs/tags/hdf5-1_14_2.tar.gz

    #
    # NETCDF-C
    #
    wget -nc https://downloads.unidata.ucar.edu/netcdf-c/$Netcdf_C_Version/netcdf-c-$Netcdf_C_Version.tar.gz

    #
    # NETCDF-FORTRAN
    #
    wget -nc https://downloads.unidata.ucar.edu/netcdf-fortran/$Netcdf_Fortran_Version/netcdf-fortran-$Netcdf_Fortran_Version.tar.gz

    #
    # PARALLEL NETCDF
    #
    echo "------------------------------"
    wget -nc https://parallel-netcdf.github.io/Release/pnetcdf-$Pnetcdf_Version.tar.gz
    echo "------------------------------"

    #
    # PIO (optional, for coupled models)
    #
    wget -nc https://github.com/NCAR/ParallelIO/archive/refs/tags/pio$Pio_Version.tar.gz
    #wget -nc https://github.com/NCAR/ParallelIO/archive/refs/tags/pio2_5_9.tar.gz


	wget -nc https://github.com/uclouvain/openjpeg/archive/refs/tags/v$jpeg_version.tar.gz


    echo " Problens of Downlaod ? https://confluence.ecmwf.int/display/ECC/Releases"
    wget -nc  https://confluence.ecmwf.int/download/attachments/45757960/eccodes-$ecc_version-Source.tar.gz

  # Pause after downloads if PROMPTOK is enabled
    if [ "$PROMPTOK" -eq 1 ]; then
        read -p "Downloads complete. Press ENTER to continue..."
    fi
fi





# Check compiler availability
if ! command -v gfortran &>/dev/null; then
    echo "ERROR: gfortran not found. Please install it with: sudo dnf install gcc-gfortran"
    exit 1
fi

# Detect compiler versions
export GCC_VERSION=$(gcc -dumpfullversion 2>/dev/null)
export GFORTRAN_VERSION=$(gfortran -dumpfullversion 2>/dev/null)
export GXX_VERSION=$(g++ -dumpfullversion 2>/dev/null)

# Validate detection
if [[ -z "$GCC_VERSION" || -z "$GFORTRAN_VERSION" || -z "$GXX_VERSION" ]]; then
    echo "ERROR: Could not detect one or more compiler versions."
    exit 1
fi

export GCC_MAJOR=$(echo "$GCC_VERSION" | cut -d. -f1)
export GFORTRAN_MAJOR=$(echo "$GFORTRAN_VERSION" | cut -d. -f1)
export GXX_MAJOR=$(echo "$GXX_VERSION" | cut -d. -f1)

# Set workaround flags if needed
if [ "$GCC_MAJOR" -ge 10 ] || [ "$GFORTRAN_MAJOR" -ge 10 ] || [ "$GXX_MAJOR" -ge 10 ]; then
    export fallow_argument="-fallow-argument-mismatch"
    export boz_argument="-fallow-invalid-boz"
    echo ">>> GCC/GFortran version ≥ 10 detected – using workaround flags."
else
    export fallow_argument=""
    export boz_argument=""
    echo ">>> GCC/GFortran version < 10 – no workaround flags needed."
fi

[ "$PROMPTOK" -eq 1 ] && read -p ">>> Compiler version check complete. Press Enter to continue..."


#-----------------------------------------------------------------------------------
#
# Step [3] - MPICH Compilation and Installation
#
# This step extracts, configures, compiles, and installs MPICH in the specified directory ($MPI_DIR).
# It uses parallel compilation based on half the number of available CPU cores (even number only).
# Compilation flags are conditionally set based on the GCC version to address argument mismatch issues.
#
#-----------------------------------------------------------------------------------

if [ "${OPTIONS[3]}" -eq 1 ]; then
    echo ">>> [3] Starting MPICH installation..."

    cd "$DOWNLOADS" || { echo "ERROR: Cannot access download directory $DOWNLOADS"; exit 1; }

    # Remove any previous source directory
    rm -rf "mpich-$Mpich_Version/"

    # Extract the source tarball
    tar -xvzf "mpich-$Mpich_Version.tar.gz"
    cd "mpich-$Mpich_Version/" || { echo "ERROR: Cannot enter MPICH source directory"; exit 1; }

    # Configure MPICH
	if [ "$LIBS_DIR" != "$MPI_DIR" ]; then
		./configure --prefix="$MPI_DIR" --with-device=ch3  FFLAGS=$fallow_argument FCFLAGS=$fallow_argument
    else 
		./configure --prefix="$LIBS_DIR" --with-device=ch3 FFLAGS=$fallow_argument FCFLAGS=$fallow_argument
    fi

    # Compile, install and check
    make -j "$CPU_HALF_EVEN"
    make -j "$CPU_HALF_EVEN" install
    make -j "$CPU_HALF_EVEN" check

    # List installed binaries
    echo ""
    echo ">>> MPICH installed in: $MPI_BIN/bin"
    ls -ltr $MPI_DIR/bin

    # Prompt to continue if enabled
    if [ "$PROMPTOK" -eq 1 ]; then
        read -p ">>> MPICH installation complete. Press enter to continue..."
    fi
fi


#============================================
# UNIVERSAL FUNCTION TO SELECT COMPILERS
#============================================
define_compilers() {
    if [ "$PARALLEL_VERSION" -eq 1 ] && [ "$LIBS_DIR" != "$MPI_DIR" ]; then
        export COMPILERS="CC=$MPICC FC=$MPIFC CXX=$MPICXX F90=$MPIF90 F77=$MPIF77"
    else
        export COMPILERS="CC=$CC FC=$FC CXX=$CXX F90=$F90 F77=$F77"
    fi
}



#-----------------------------------------------------------------------------------
# ===============================
#        ZLIB Installation
# ===============================
if [ "${OPTIONS[4]}" -eq 1 ]; then
    define_compilers
    cd "$DOWNLOADS"
    rm -rf "zlib-$Zlib_Version/"
    tar -xvzf "zlib-$Zlib_Version.tar.gz"
    cd "zlib-$Zlib_Version/"

    eval "$COMPILERS FCFLAGS=\"$FCFLAGS\" CFLAGS=\"$CFLAGS\" ./configure --prefix=\"$LIBS_DIR/\""
    make -j "$CPU_HALF_EVEN"
    make -j "$CPU_HALF_EVEN" install

    echo -e "\n>> ZLIB installed in $LIBS_DIR/lib"
    ls -ltr "$LIBS_DIR/lib"
    [ "$PROMPTOK" -eq 1 ] && read -p "ZLIB installed. Press enter to continue..."
fi

# ===============================
#        LIBPNG Installation
# ===============================
if [ "${OPTIONS[5]}" -eq 1 ]; then
    define_compilers
    cd "$DOWNLOADS"
    rm -rf "libpng-$Libpng_Version/"
    tar -xvzf "libpng-$Libpng_Version.tar.gz"
    cd "libpng-$Libpng_Version/"

    autoreconf -i -f
    eval "$COMPILERS FCFLAGS=\"$FCFLAGS\" CFLAGS=\"$CFLAGS\" ./configure --prefix=\"$LIBS_DIR/\""
    automake -a -f
    make -j "$CPU_HALF_EVEN"
    make -j "$CPU_HALF_EVEN" install

    echo -e "\n>> LIBPNG installed in $LIBS_DIR/lib"
    ls -ltr "$LIBS_DIR/lib"
    [ "$PROMPTOK" -eq 1 ] && read -p "LIBPNG installed. Press enter to continue..."
fi

# ===============================
#        JASPER Installation
# ===============================
if [ "${OPTIONS[6]}" -eq 1 ]; then
    define_compilers
    cd "$DOWNLOADS"
    rm -rf "jasper-$Jasper_Version/"
    unzip "jasper-$Jasper_Version.zip"
    cd "jasper-$Jasper_Version/"

    autoreconf -i
    eval "$COMPILERS FCFLAGS=\"$FCFLAGS\" CFLAGS=\"$CFLAGS\" ./configure --prefix=\"$LIBS_DIR/\""
    automake -a -f
    make -j "$CPU_HALF_EVEN"
    make -j "$CPU_HALF_EVEN" install

    echo -e "\n>> JASPER installed in $LIBS_DIR/lib"
    ls -ltr "$LIBS_DIR/lib"
    [ "$PROMPTOK" -eq 1 ] && read -p "JASPER installed. Press enter to continue..."
fi

# ===============================
#       HDF5 Installation
# ===============================
if [ "${OPTIONS[7]}" -eq 1 ]; then
    define_compilers
    cd "$DOWNLOADS"
    rm -rf "hdf5-$HDF5_Version"
    tar -xvzf "hdf5-$HDF5_Version.tar.gz"
    cd hdf5-hdf5-$HDF5_Version

    autoreconf -i -f
    eval "$COMPILERS FCFLAGS=\"$FCFLAGS\" CFLAGS=\"$CFLAGS\" ./configure --prefix=\"$LIBS_DIR/\" --with-zlib=\"$LIBS_DIR/\" --enable-hl --enable-fortran --disable-shared"
    automake -a -f
    make -j "$CPU_HALF_EVEN"
    make -j "$CPU_HALF_EVEN" install

    echo -e "\n>> HDF5 installed in $LIBS_DIR/lib"
    ls -ltr "$LIBS_DIR/lib"
    [ "$PROMPTOK" -eq 1 ] && read -p "HDF5 installed. Press enter to continue..."
fi

# ===============================
#       PNETCDF Installation
# ===============================
if [ "${OPTIONS[8]}" -eq 1 ]; then
    define_compilers
    cd "$DOWNLOADS"
    rm -rf "pnetcdf-$Pnetcdf_Version"
    tar -xvzf "pnetcdf-$Pnetcdf_Version.tar.gz"
    cd "pnetcdf-$Pnetcdf_Version"

    autoreconf -i -f
    eval "$COMPILERS FCFLAGS=\"$FCFLAGS\" CFLAGS=\"$CFLAGS\" ./configure --prefix=\"$LIBS_DIR/\""
    automake -a -f
    make -j "$CPU_HALF_EVEN"
    make -j "$CPU_HALF_EVEN" install
    make -j "$CPU_HALF_EVEN" check

    echo -e "\n>> PNETCDF installed in $LIBS_DIR/lib"
    ls -ltr "$LIBS_DIR/lib"
    [ "$PROMPTOK" -eq 1 ] && read -p "PNETCDF installed. Press enter to continue..."
fi

# ===============================
#       NETCDF-C Installation
# ===============================
if [ "${OPTIONS[9]}" -eq 1 ]; then
    define_compilers
    cd "$DOWNLOADS"
    rm -rf "netcdf-c-$Netcdf_C_Version"
    tar -xzvf "netcdf-c-$Netcdf_C_Version.tar.gz"
    cd "netcdf-c-$Netcdf_C_Version"

    autoreconf -i -f
    eval "$COMPILERS CPPFLAGS=\"-I$LIBS_DIR/include\" LDFLAGS=\"-L$LIBS_DIR/lib\" ./configure --prefix=\"$NETCDF\" --disable-dap --disable-byterange --disable-libxml2 --enable-netcdf4 --enable-cdf5 --disable-shared"
    automake -a -f
    make -j "$CPU_HALF_EVEN"
    make -j "$CPU_HALF_EVEN" check
    make -j "$CPU_HALF_EVEN" install

    echo -e "\n>> NETCDF-C installed in $LIBS_DIR/lib"
    ls -ltr "$LIBS_DIR/lib"
    [ "$PROMPTOK" -eq 1 ] && read -p "NETCDF-C installed. Press enter to continue..."
fi

# ===============================
#   NETCDF-FORTRAN Installation
# ===============================
if [ "${OPTIONS[10]}" -eq 1 ]; then
    define_compilers
    cd "$DOWNLOADS"
    rm -rf "netcdf-fortran-$Netcdf_Fortran_Version"
    tar -xvzf "netcdf-fortran-$Netcdf_Fortran_Version.tar.gz"
    cd "netcdf-fortran-$Netcdf_Fortran_Version"

    autoreconf -i -f
    eval "$COMPILERS CPPFLAGS=\"-I$LIBS_DIR/include -I$NETCDF/include\" LDFLAGS=\"-L$LIBS_DIR/lib -L$NETCDF/lib\" LIBS=\"-lhdf5_hl -lhdf5 -lz -ldl\" ./configure --prefix=\"$NETCDF\" --disable-shared"
    automake -a -f
    make -j "$CPU_HALF_EVEN"
    make -j "$CPU_HALF_EVEN" check
    make -j "$CPU_HALF_EVEN" install

    echo -e "\n>> NETCDF-FORTRAN installed in $LIBS_DIR/lib"
    ls -ltr "$LIBS_DIR/lib"
    [ "$PROMPTOK" -eq 1 ] && read -p "NETCDF-FORTRAN installed. Press enter to continue..."
fi

# ===============================
#            PIO
# ===============================
if [ "${OPTIONS[11]}" -eq 1 ]; then
    define_compilers

    cd "$DOWNLOADS"
    rm -rf ParallelIO-pio$Pio_Version
    tar -xzvf pio$Pio_Version.tar.gz
    cd ParallelIO-pio$Pio_Version
    mkdir -p pio && cd pio
    export PIOSRC="$DOWNLOADS/ParallelIO-pio$Pio_Version/"

    # Compilação com MPI
    CC=$MPICC FC=$MPIFC CXX=$MPICXX F90=$MPIF90 F77=$MPIF77 \
    cmake -DNetCDF_C_PATH=$LIBS_DIR \
          -DNetCDF_Fortran_PATH=$LIBS_DIR \
          -DPnetCDF_PATH=$LIBS_DIR \
          -DHDF5_PATH=$LIBS_DIR \
          -DCMAKE_INSTALL_PREFIX=$LIBS_DIR \
          -DPIO_USE_MALLOC=ON \
          -DCMAKE_VERBOSE_MAKEFILE=1 \
          -DPIO_ENABLE_TIMING=OFF \
          $PIOSRC

    make -j "$CPU_HALF_EVEN"
    make -j "$CPU_HALF_EVEN" install

    echo -e "\n>> PIO installed in $LIBS_DIR/lib"
    ls -ltr "$LIBS_DIR/lib"
    [ "$PROMPTOK" -eq 1 ] && read -p "PIO installed. Press enter to continue..."
fi





##-----------------------------------------------------------------------------------
#
#                    WRF
#
#

# Check if the WRF installation option is enabled
if [ "${OPTIONS[12]}" -eq 1 ]; then

    echo ">> Starting WRF installation..."
	# Enable support for large NetCDF files
	export WRFIO_NCD_LARGE_FILE_SUPPORT=1
	
    # Set compiler flags to include headers and link libraries from NetCDF and MPI
    export CPPFLAGS="-I$LIBS_DIR/include -I$MPI_DIR/include"
    export LDFLAGS="-L$LIBS_DIR/lib -L$MPI_DIR/lib"

    # Navigate to the installation directory and clone the WRF repository
    cd $INSTALL_DIR
    rm -rf WRF  # Remove any previous WRF directory to avoid conflicts
    git clone https://github.com/wrf-model/WRF.git
    cd WRF

    # Clean any previous build artifacts
    ./clean

    # Launch interactive configuration
    # Option 34 = dmpar (distributed memory) + gfortran
    # Option 1  = basic nesting
    ./configure

    # Optional manual review/editing of configure.wrf file
    #vim configure.wrf

    # Compile WRF with parallel jobs based on available CPU cores
    ./compile -j "$CPU_HALF_EVEN" em_real

    # Display the resulting executables
    echo -e "\n>> WRF build completed."
    ls -ltr main/*.exe

    # Prompt user to continue (if enabled)
    [ "$PROMPTOK" -eq 1 ] && read -p "WRF build done. Press enter to continue..."
fi


#-----------------------------------------------------------------------------------
#
#
#                  WPS 
#
# Check if the WPS installation option is enabled
if [ "${OPTIONS[13]}" -eq 1 ]; then
    echo ">> Starting WPS installation..."

    # Navigate to the installation directory and clone the WPS repository
	# Set compiler flags to include headers and link libraries from NetCDF and MPI
    export CPPFLAGS="-I$LIBS_DIR/include -I$MPI_DIR/include"
    export LDFLAGS="-L$LIBS_DIR/lib -L$MPI_DIR/lib"
	export LIBS="-lhdf5_hl -lhdf5 -lz -ldl"
	cd $INSTALL_DIR
	rm -rf WPS

    git clone https://github.com/wrf-model/WPS.git
    cd WPS

    # Clean any previous build artifacts
    ./clean

    # Launch interactive configuration
    # Option 3 = gfortran with distributed memory support
    ./configure
	#
	#  Force the HDF5 libraries to be included in the WPS configuration
	#
    sed -i 's|-L$(NETCDF)/lib -lnetcdff -lnetcdf|-L$(NETCDF)/lib -lnetcdff -lnetcdf -lhdf5_hl -lhdf5 -lz -ldl|' configure.wps
     #vim configure.wps 
    # Compile WPS using parallel jobs based on available CPU cores
    ./compile  

    # Display the resulting executables
    echo -e "\n>> WPS build completed."
    ls -ltr geogrid/src/geogrid.exe metgrid/src/metgrid.exe ungrib/src/ungrib.exe

    # Prompt user to continue (if enabled)
    [ "$PROMPTOK" -eq 1 ] && read -p "WPS build done. Press enter to continue..."
fi



#-----------------------------------------------------------------------------------
################################# MPAS-ATMOSPHERE ################################
# USE_PIO2 over PIO1 due to error, shouldn't affect build
##################################################################################
if [ "${OPTIONS[14]}" -eq 1 ]; then
    echo ">> Starting MPAS installation..."
    #
    #
    
	
	cd "$INSTALL_DIR"
	rm -rf MPAS-Model 
	git clone https://github.com/MPAS-Dev/MPAS-Model.git
	cd MPAS-Model
	export MPAS_EXTERNAL_LIBS="-L$LIBS_DIR/lib -lnetcdf -lpnetcdf -lhdf5_hl -lhdf5 -ldl -lz"
	export MPAS_EXTERNAL_INCLUDES="-I$LIBS_DIR/include"
	
	# GNU 
	if [ "$COMPILER" == "GNU" ]; then
	    echo ">> MPAS compiling GNU "
		make gfortran CORE=init_atmosphere USE_PIO2=true PRECISION=single
		make clean CORE=atmosphere USE_PIO2=true PRECISION=single
		make gfortran CORE=atmosphere USE_PIO2=true PRECISION=single
	elif [ "$COMPILER" == "INTEL" ]; then
		echo ">> MPAS compiling INTEL "
		make intel CORE=init_atmosphere USE_PIO2=true PRECISION=single
		make clean CORE=atmosphere USE_PIO2=true PRECISION=single
		make gfortran CORE=atmosphere USE_PIO2=true PRECISION=single
	elif [ "$COMPILER" == "NVIDIA" ]; then
		echo "> compiling NVIDIA HPC "
		make nvhpc CORE=init_atmosphere USE_PIO2=true PRECISION=single
		make clean CORE=atmosphere USE_PIO2=true PRECISION=single
		make gfortran CORE=atmosphere USE_PIO2=true PRECISION=single
    fi 

    # Prompt user to continue (if enabled)
    [ "$PROMPTOK" -eq 1 ] && read -p "MPAS build done. Press enter to continue..."

fi 



