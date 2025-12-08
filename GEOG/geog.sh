  #!/bin/bash 


  export GEOG=/umbral/GEOG/ 
  export Downloads=~/Downloads 

  
  
  cd "$DOWNLOADS"

    wget -nc https://www2.mmm.ucar.edu/wrf/src/wps_files/geog_high_res_mandatory.tar.gz
    wget -nc https://www2.mmm.ucar.edu/wrf/src/wps_files/geog_noahmp.tar.gz
    wget -nc https://www2.mmm.ucar.edu/wrf/src/wps_files/geog_thompson28_chem.tar.gz
    wget -nc https://www2.mmm.ucar.edu/wrf/src/wps_files/irrigation.tar.gz
    wget -nc https://www2.mmm.ucar.edu/wrf/src/wps_files/geog_px.tar.gz
    wget -nc https://www2.mmm.ucar.edu/wrf/src/wps_files/geog_urban.tar.gz
    wget -nc https://www2.mmm.ucar.edu/wrf/src/wps_files/geog_ssib.tar.gz
    wget -nc https://www2.mmm.ucar.edu/wrf/src/wps_files/lake_depth.tar.bz2
    wget -nc https://www2.mmm.ucar.edu/wrf/src/wps_files/modis_landuse_20class_30s_with_lakes.tar.bz2
    wget -nc https://www2.mmm.ucar.edu/wrf/src/wps_files/modis_landuse_20class_30s.tar.bz2
  wget -nc https://www2.mmm.ucar.edu/wrf/src/wps_files/topo_gmted2010_30s.tar.bz2
  wget -nc https://www2.mmm.ucar.edu/wrf/src/wps_files/soiltype_top_30s.tar.bz2
  wget -nc https://www2.mmm.ucar.edu/wrf/src/wps_files/soiltemp_1deg.tar.bz2
  wget -nc https://www2.mmm.ucar.edu/wrf/src/wps_files/maxsnowalb.tar.bz2
  wget -nc https://www2.mmm.ucar.edu/wrf/src/wps_files/maxsnowalb_modis.tar.bz2
  wget -nc https://www2.mmm.ucar.edu/wrf/src/wps_files/greenfrac_fpar_modis.tar.bz2
  wget -nc https://www2.mmm.ucar.edu/wrf/src/wps_files/geog_new3.9.tar.bz2
  wget -nc https://www2.mmm.ucar.edu/wrf/src/wps_files/geog_complete.tar.gz
  wget -nc https://www2.mmm.ucar.edu/wrf/src/wps_files/albedo_modis.tar.bz2
  wget -nc https://www2.mmm.ucar.edu/wrf/src/wps_files/gsl_gwd.tar.bz2
  wget -nc https://www2.mmm.ucar.edu/wrf/src/wps_files/geog_low_res_mandatory.tar.gz
  wget -nc https://www2.mmm.ucar.edu/wrf/src/wps_files/topo_30s.tar.bz2


mkdir -p $GEOG/WPS_GEOG

    # tar -xvzf $DOWNLOADS/geog_high_res_mandatory.tar.gz 
     cd $GEOG/WPS_GEOG
    #tar -xvf $DOWNLOADS/topo_30s.tar.bz2 
    #tar -xvf  $DOWNLOADS/geog_low_res_mandatory.tar.gz
    tar -xvf $DOWNLOADS/geog_new3.9.tar.bz2
    tar -xvf  $DOWNLOADS/geog_complete.tar.gz
    #tar -xvf $DOWNLOADS/albedo_modis.tar.bz2
    #tar -xvf $DOWNLOADS/gsl_gwd.tar.bz2
#tar -xvzf $DOWNLOADS/geog_thompson28_chem.tar.gz 
    #tar -xvzf $DOWNLOADS/geog_noahmp.tar.gz
    #tar -xvzf $DOWNLOADS/irrigation.tar.gz 
    #tar -xvzf $DOWNLOADS/geog_px.tar.gz 
    #tar -xvzf $DOWNLOADS/geog_urban.tar.gz 
    #tar -xvf $DOWNLOADS/lake_depth.tar.bz2 
    #tar -xvf $DOWNLOADS/modis_landuse_20class_30s_with_lakes.tar.bz2 
    #tar -xvf $DOWNLOADS/modis_landuse_20class_30s.tar.bz2 
    #tar -xvf $DOWNLOADS/topo_gmted2010_30s.tar.bz2
   # tar -xvf $DOWNLOADS/soiltype_top_30s.tar.bz2
#    tar -xvf $DOWNLOADS/soiltemp_1deg.tar.bz2


#tar -xvf $DOWNLOADS/maxsnowalb.tar.bz2 
#tar -xvf $DOWNLOADS/maxsnowalb_modis.tar.bz2
#tar -xvf $DOWNLOADS/greenfrac_fpar_modis.tar.bz2

