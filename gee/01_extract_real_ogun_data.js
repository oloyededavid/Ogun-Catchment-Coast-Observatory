var hybas7 = ee.FeatureCollection('WWF/HydroSHEDS/v1/Basins/hybas_7');
var rivers = ee.FeatureCollection('WWF/HydroSHEDS/v1/FreeFlowingRivers');
var jrc = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence').unmask(0);


// ---------------------------------------------------------------------------
// Sub-basin delineation by HydroBASINS topology (NEXT_DOWN upstream tracing).
// Each zone is defined by a POUR POINT (outlet). A zone is the hybas_7 unit that
// contains its pour point plus every unit draining into it, minus any upstream
// zone already assigned. No latitude/longitude slicing is used.
//
// VERIFY BEFORE EXPORT: check each pour point on the map (layers are added
// below) and move it if it does not sit on the intended outlet reach.
// ---------------------------------------------------------------------------
var POUR_POINTS = {
  // Oyan Dam outlet: everything upstream = Oyan-Ofiki regulated tributary (Z2)
  oyanDam: ee.Geometry.Point([3.26, 7.25]),
  // Upper Ogun mainstem outlet (above the Oyan confluence): upstream = Z1
  upperOgunOutlet: ee.Geometry.Point([3.45, 7.75]),
  // Ogun mainstem at Abeokuta: upstream minus Z1, Z2 = Middle Ogun (Z3)
  abeokuta: ee.Geometry.Point([3.35, 7.15])
};

var mainBasId = hybas7.filterBounds(POUR_POINTS.abeokuta).first().get('MAIN_BAS');
var ogunHybas7 = hybas7.filter(ee.Filter.eq('MAIN_BAS', mainBasId));

// Returns the HYBAS_IDs of the unit containing `pt` and all units upstream of it.
function upstreamIds(pt) {
  var outletId = ogunHybas7.filterBounds(pt).first().get('HYBAS_ID');
  var seed = ee.List([outletId]);
  // 80 iterations exceeds the longest hybas_7 flow path in the Ogun basin.
  return ee.List(ee.List.sequence(1, 80).iterate(function(_, acc) {
    acc = ee.List(acc);
    var newIds = ogunHybas7.filter(ee.Filter.inList('NEXT_DOWN', acc))
      .aggregate_array('HYBAS_ID');
    return acc.cat(newIds).distinct();
  }, seed));
}

var idsZ2 = upstreamIds(POUR_POINTS.oyanDam);
var idsZ1 = upstreamIds(POUR_POINTS.upperOgunOutlet).removeAll(idsZ2);
var idsZ3 = upstreamIds(POUR_POINTS.abeokuta).removeAll(idsZ1).removeAll(idsZ2);
var idsAssigned = idsZ1.cat(idsZ2).cat(idsZ3);
var idsZ4 = ogunHybas7.filter(ee.Filter.inList('HYBAS_ID', idsAssigned).not())
  .aggregate_array('HYBAS_ID');

function zoneGeom(ids) {
  return ogunHybas7.filter(ee.Filter.inList('HYBAS_ID', ids)).geometry().dissolve();
}

var z1Geom = zoneGeom(idsZ1);
var z2Geom = zoneGeom(idsZ2);
var z3Geom = zoneGeom(idsZ3);
var z4Geom = zoneGeom(idsZ4);
var catchmentGeom = ogunHybas7.geometry().dissolve();

// Sanity check: every basin unit assigned exactly once.
print('hybas_7 units per zone (Z1, Z2, Z3, Z4):',
  idsZ1.size(), idsZ2.size(), idsZ3.size(), idsZ4.size());
print('Total Ogun hybas_7 units (must equal the sum above):', ogunHybas7.size());
Map.addLayer(ee.FeatureCollection([
  ee.Feature(POUR_POINTS.oyanDam, {name: 'Oyan Dam'}),
  ee.Feature(POUR_POINTS.upperOgunOutlet, {name: 'Upper Ogun outlet'}),
  ee.Feature(POUR_POINTS.abeokuta, {name: 'Abeokuta'})
]), {color: 'red'}, 'Pour points (verify)');

var estuaryRawBox = ee.Geometry.Polygon([
  [[3.32, 6.45], [3.51, 6.45], [3.51, 6.58], [3.32, 6.58], [3.32, 6.45]]
]);
var estuaryGeom = estuaryRawBox.difference(catchmentGeom, 30);

var SCRIPT_VERSION = '2.0.0';
var EXPORT_UTC = ee.Date(Date.now()).format('YYYY-MM-dd\'T\'HH:mm:ss\'Z\'', 'UTC');

function makeUnitFeature(geom, id, order, name, unitType, regime, color, summary, management) {
  var areaKm2 = geom.area(10).divide(1e6);
  return ee.Feature(geom, {
    'zone_id': id,
    'order': order,
    'zone_name': name,
    'unit_type': unitType,
    'regime': regime,
    'role_color': color,
    'area_km2': areaKm2,
    'summary': summary,
    'management': management,
    'provenance': 'VERIFIED_GEE_EXPORT',
    'export_utc': EXPORT_UTC,
    'script_version': SCRIPT_VERSION,
    'crs': 'EPSG:4326'
  });
}

var analyticalUnits = ee.FeatureCollection([
  makeUnitFeature(
    z1Geom, 'Z1', 1, 'Upper Ogun Headwaters Sub-Basin', 'Hydrological Sub-Basin (hybas_7)',
    'Basement Runoff Core', '#0284C7',
    'Precambrian basement headwaters in northern Oyo State delineated from intact WWF HydroBASINS L7 units. Shallow saprolite soils and steeper slopes generate seasonal infiltration-excess overland flow.',
    'Maintain upland gallery forest buffers and contour soil-conservation practices along headwater tributaries.'
  ),
  makeUnitFeature(
    z2Geom, 'Z2', 2, 'Oyan-Ofiki Tributary Sub-Basin', 'Hydrological Sub-Basin (hybas_7)',
    'Regulated Tributary Sub-Basin', '#0D9488',
    'Western crystalline tributary sub-basin draining the Ofiki and Oyan rivers into the Oyan Reservoir upstream of Abeokuta.',
    'Integrate telemetric stage monitoring with reservoir operating records where gauge data are available.'
  ),
  makeUnitFeature(
    z3Geom, 'Z3', 3, 'Middle Ogun Mainstem Sub-Basin', 'Hydrological Sub-Basin (hybas_7)',
    'Mainstem Fluvial Corridor', '#D97706',
    'Confluence sub-basin below the Oyan tributary junction spanning Abeokuta, Papalanto, Ewekoro, and Ifo across the basement-to-sedimentary transition.',
    'Preserve non-buildable fluvial setback corridors and monitor bank stability along braided mainstem reaches.'
  ),
  makeUnitFeature(
    z4Geom, 'Z4', 4, 'Lower Ogun Alluvial Corridor', 'Hydrological Sub-Basin (hybas_7)',
    'Low-Gradient Alluvial Floodplain', '#DC2626',
    'Low-gradient alluvial floodplain sub-basin spanning Mowe, Kara, Isheri, Akute, and Ikorodu West where low terrain slope (< 1 deg) promotes seasonal ponding.',
    'Restrict wetland reclamation in low-lying alluvial floodplains to preserve natural flood storage capacity.'
  ),
  makeUnitFeature(
    estuaryGeom, 'Z5', 5, 'Northwest Lagos Lagoon Estuary', 'Estuarine Receiving Zone (Non-Watershed)',
    'Estuarine Mixing Zone', '#7C2D12',
    'Downstream estuarine receiving environment where the Ogun River discharges into the northwest Lagos Lagoon. Evaluated specifically for open-water spectral turbidity (NDTI).',
    'Combine satellite NDTI plume monitoring with in-situ gravimetric TSS sampling and coastal wetland conservation.'
  )
]);

var fullStudyGeom = analyticalUnits.geometry().dissolve();
var ogunRivers = rivers.filterBounds(fullStudyGeom).filter(ee.Filter.gte('ORD_STRA', 3));
var riparianCorridorGeom = ogunRivers.geometry().buffer(2000).intersection(fullStudyGeom, 30);

Map.centerObject(fullStudyGeom, 8);
Map.addLayer(analyticalUnits, {}, 'Audited Hydrological & Estuarine Units');
Map.addLayer(ogunRivers, {color: '#0284C7'}, 'HydroSHEDS River Network (Order >= 3)');


var startDateStr = '2019-01-01';
// filterDate end is exclusive: use the first day after the study period.
var endDateStr = '2025-01-01';
var dem = ee.ImageCollection('COPERNICUS/DEM/GLO30').select('DEM').mosaic().clip(fullStudyGeom);
var slope = ee.Terrain.slope(dem).rename('slope_deg');
var lowSlopeMask = slope.lt(5.0);
var seasonalDomainMask = jrc.lt(80);
var openEstuaryWaterMask = jrc.gte(50);

// Oyan Reservoir domain: JRC maximum water extent inside a box around the
// reservoir. Monthly Sentinel-1 open-water area inside it is a proxy for
// reservoir storage/regulation (no public release records are available).
// VERIFY the box covers the whole reservoir and nothing else.
var jrcMaxExtent = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('max_extent');
var oyanBox = ee.Geometry.Rectangle([3.10, 7.22, 3.40, 7.50]);
var oyanReservoirMask = jrcMaxExtent.eq(1).clip(oyanBox);
Map.addLayer(oyanReservoirMask.selfMask(), {palette: ['#7C3AED']}, 'Oyan Reservoir domain (verify)');

function preprocessS2(img) {
  var scl = img.select('SCL');
  var clearMask = scl.neq(1).and(scl.neq(2)).and(scl.neq(3))
    .and(scl.neq(8)).and(scl.neq(9)).and(scl.neq(10)).and(scl.neq(11));

  var mndwi = img.normalizedDifference(['B3', 'B11']);
  var isWater = mndwi.gt(0.0).and(scl.eq(6));
  var isLand = mndwi.lte(0.0).and(scl.neq(6));

  var ndti = img.normalizedDifference(['B4', 'B3']).rename('ndti')
    .updateMask(clearMask.and(isWater));

  var ndvi = img.normalizedDifference(['B8', 'B4']).rename('ndvi')
    .updateMask(clearMask.and(isLand));

  return ndti.addBands(ndvi).copyProperties(img, ['system:time_start']);
}

var s2Processed = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(fullStudyGeom)
  .filterDate(startDateStr, endDateStr)
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 70))
  .map(preprocessS2);

var s1Collection = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(fullStudyGeom)
  .filterDate(startDateStr, endDateStr)
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.eq('orbitProperties_pass', 'DESCENDING'))
  .select('VV');


var meanAnnualRain = ee.ImageCollection('UCSB-CHG/CHIRPS/PENTAD')
  .filterDate(startDateStr, endDateStr)
  .select('precipitation')
  .sum()
  .divide(6.0)
  .rename('rain_mm');

var meanShallowSm = ee.ImageCollection('ECMWF/ERA5_LAND/MONTHLY_AGGR')
  .filterDate(startDateStr, endDateStr)
  .select('volumetric_soil_water_layer_1')
  .mean()
  .rename('shallow_sm_m3m3');

var s1Peak2022 = s1Collection
  .filterDate('2022-09-01', '2022-10-31')
  .map(function(img) { return img.focal_median(50, 'circle', 'meters'); })
  .median();

var sarPeakProxyKm2 = s1Peak2022.lt(-16.5)
  .and(lowSlopeMask)
  .and(seasonalDomainMask)
  .multiply(ee.Image.pixelArea())
  .divide(1e6)
  .rename('sar_inundation_km2');

var permanentWaterKm2 = jrc.gte(80)
  .multiply(ee.Image.pixelArea())
  .divide(1e6)
  .rename('perm_water_km2');

var s2MultiYear = s2Processed.median();

var enrichedUnits = analyticalUnits.map(function(feat) {
  var geom = feat.geometry();
  var riparianSub = geom.intersection(riparianCorridorGeom, 30);

  var climateSlopeStats = meanAnnualRain.addBands([meanShallowSm, slope]).reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: geom,
    scale: 100,
    maxPixels: 1e10
  });

  var waterStats = s2MultiYear.select('ndti').reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: geom,
    scale: 30,
    maxPixels: 1e10
  });

  var riparianStats = s2MultiYear.select('ndvi').reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: riparianSub,
    scale: 30,
    maxPixels: 1e10
  });

  var inundationSum = sarPeakProxyKm2.addBands(permanentWaterKm2).reduceRegion({
    reducer: ee.Reducer.sum(),
    geometry: geom,
    scale: 60,
    maxPixels: 1e10
  });

  return feat.simplify(30)
    .set(climateSlopeStats)
    .set(waterStats)
    .set(riparianStats)
    .set(inundationSum);
});

Export.table.toDrive({
  collection: enrichedUnits,
  description: 'ogun_subbasins',
  fileFormat: 'GeoJSON'
});


var chirpsCol = ee.ImageCollection('UCSB-CHG/CHIRPS/PENTAD').select('precipitation');
var era5Col = ee.ImageCollection('ECMWF/ERA5_LAND/MONTHLY_AGGR').select('volumetric_soil_water_layer_1');

var maskedChirpsTemplate = ee.Image.constant(0).rename('precipitation').updateMask(ee.Image.constant(0));
var maskedEra5Template = ee.Image.constant(0).rename('volumetric_soil_water_layer_1').updateMask(ee.Image.constant(0));
var maskedS1Template = ee.Image.constant(0).rename('VV').updateMask(ee.Image.constant(0));
var maskedS2Template = ee.Image.constant([0, 0]).rename(['ndti', 'ndvi']).updateMask(ee.Image.constant(0));

var months = ee.List.sequence(0, 71);
var baseDate = ee.Date(startDateStr);

// Builds the monthly images once; reduced over the catchment, each unit and
// the Oyan Reservoir below.
function monthImages(m) {
  var mStart = baseDate.advance(m, 'month');
  var mEnd = mStart.advance(1, 'month');

  var chirpsMonth = chirpsCol.filterDate(mStart, mEnd);
  var era5Month = era5Col.filterDate(mStart, mEnd);
  var s1Month = s1Collection.filterDate(mStart, mEnd)
    .map(function(img) { return img.focal_median(50, 'circle', 'meters'); });
  var s2Month = s2Processed.filterDate(mStart, mEnd);

  var s1MedImg = ee.ImageCollection([maskedS1Template]).merge(s1Month).median();
  var s2MedImg = ee.ImageCollection([maskedS2Template]).merge(s2Month).median();

  return {
    yearMonth: mStart.format('YYYY-MM'),
    pentadCount: chirpsMonth.size(),
    era5Count: era5Month.size(),
    s1Count: s1Month.size(),
    s2SceneCount: s2Month.size(),
    rainImg: ee.ImageCollection([maskedChirpsTemplate]).merge(chirpsMonth).sum(),
    smImg: ee.ImageCollection([maskedEra5Template]).merge(era5Month).mean(),
    sarAreaImg: s1MedImg.lt(-16.5)
      .and(lowSlopeMask)
      .and(seasonalDomainMask)
      .multiply(ee.Image.pixelArea())
      .divide(1e6)
      .rename('VV'),
    reservoirAreaImg: s1MedImg.lt(-16.5)
      .and(oyanReservoirMask)
      .multiply(ee.Image.pixelArea())
      .divide(1e6)
      .rename('VV'),
    ndtiImg: s2MedImg.select('ndti').updateMask(openEstuaryWaterMask)
  };
}

function reduceMean(img, band, geom, scale) {
  return img.reduceRegion({reducer: ee.Reducer.mean(), geometry: geom, scale: scale, maxPixels: 1e9}).get(band);
}

function reduceSum(img, geom, scale) {
  return img.reduceRegion({reducer: ee.Reducer.sum(), geometry: geom, scale: scale, maxPixels: 1e9}).get('VV');
}

function ndtiStats(mi, geom) {
  var px = ee.Number(mi.ndtiImg.reduceRegion({
    reducer: ee.Reducer.count(), geometry: geom, scale: 30, maxPixels: 1e9
  }).get('ndti', 0));
  var mean = reduceMean(mi.ndtiImg, 'ndti', geom, 30);
  return {px: px, ndti: ee.Algorithms.If(px.gte(100), mean, null)};
}

// --- Catchment-wide monthly series (Z1-Z4 rain, soil water, SAR; Z5 NDTI) ---
var monthlyTimeSeries = ee.FeatureCollection(months.map(function(m) {
  var mi = monthImages(m);
  var nd = ndtiStats(mi, estuaryGeom);
  return ee.Feature(null, {
    'year_month': mi.yearMonth,
    'rain_mm': ee.Algorithms.If(mi.pentadCount.gte(5), reduceMean(mi.rainImg, 'precipitation', catchmentGeom, 5500), null),
    'shallow_sm_m3m3': ee.Algorithms.If(mi.era5Count.gt(0), reduceMean(mi.smImg, 'volumetric_soil_water_layer_1', catchmentGeom, 9000), null),
    'sar_flood_km2': ee.Algorithms.If(mi.s1Count.gt(0), reduceSum(mi.sarAreaImg, catchmentGeom, 120), null),
    'oyan_reservoir_km2': ee.Algorithms.If(mi.s1Count.gt(0), reduceSum(mi.reservoirAreaImg, oyanBox, 30), null),
    'estuary_ndti': nd.ndti,
    'chirps_pentads': mi.pentadCount,
    's1_scenes': mi.s1Count,
    's2_clear_scenes': mi.s2SceneCount,
    's2_water_px': nd.px,
    'export_utc': EXPORT_UTC,
    'script_version': SCRIPT_VERSION,
    'data_status': 'VERIFIED_GEE_EXPORT'
  });
}));

Export.table.toDrive({
  collection: monthlyTimeSeries,
  description: 'ogun_monthly_timeseries',
  fileFormat: 'CSV'
});

// --- Per-unit monthly series (5 units x 72 months) ---------------------------
// NDTI is reported for Z5 (estuary open water) only; SAR for Z1-Z4 only.
var unitGeoms = ee.List([
  ['Z1', z1Geom], ['Z2', z2Geom], ['Z3', z3Geom], ['Z4', z4Geom], ['Z5', estuaryGeom]
]);

var unitMonthly = ee.FeatureCollection(months.map(function(m) {
  var mi = monthImages(m);
  return ee.FeatureCollection(unitGeoms.map(function(pair) {
    pair = ee.List(pair);
    var zoneId = ee.String(pair.get(0));
    var geom = ee.Geometry(pair.get(1));
    var isEstuary = zoneId.equals('Z5');
    var nd = ndtiStats(mi, geom);
    return ee.Feature(null, {
      'zone_id': zoneId,
      'year_month': mi.yearMonth,
      'rain_mm': ee.Algorithms.If(mi.pentadCount.gte(5), reduceMean(mi.rainImg, 'precipitation', geom, 5500), null),
      'shallow_sm_m3m3': ee.Algorithms.If(mi.era5Count.gt(0), reduceMean(mi.smImg, 'volumetric_soil_water_layer_1', geom, 9000), null),
      'sar_flood_km2': ee.Algorithms.If(isEstuary, null, ee.Algorithms.If(mi.s1Count.gt(0), reduceSum(mi.sarAreaImg, geom, 120), null)),
      'estuary_ndti': ee.Algorithms.If(isEstuary, nd.ndti, null),
      's1_scenes': mi.s1Count,
      's2_water_px': ee.Algorithms.If(isEstuary, nd.px, null),
      'export_utc': EXPORT_UTC,
      'script_version': SCRIPT_VERSION,
      'data_status': 'VERIFIED_GEE_EXPORT'
    });
  }));
})).flatten();

Export.table.toDrive({
  collection: unitMonthly,
  description: 'ogun_unit_monthly_timeseries',
  fileFormat: 'CSV'
});
