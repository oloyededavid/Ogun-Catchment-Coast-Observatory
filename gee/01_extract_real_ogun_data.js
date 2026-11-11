var hybas9 = ee.FeatureCollection('WWF/HydroSHEDS/v1/Basins/hybas_9');
var rivers = ee.FeatureCollection('WWF/HydroSHEDS/v1/FreeFlowingRivers');
var jrc = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence').unmask(0);


// ---------------------------------------------------------------------------
// Sub-basin delineation by HydroBASINS level-9 topology (NEXT_DOWN tracing).
//
// A zone is everything upstream of an OUTLET unit, minus zones further upstream.
// Outlets are fixed HydroBASINS v1 level-9 HYBAS_IDs, checked against UP_AREA:
//   1090960280  Ogun River outlet to the Lagos Lagoon   (UP_AREA 22,165.7 km2)
//   1090950490  Lower Ogun mainstem at ~6.9 N            (UP_AREA 21,322.2 km2)
//   1090928900  Upper Ogun, above the Oyan confluence    (UP_AREA  9,574.5 km2)
//   1090931470  Oyan Dam outlet (Oyan-Ofiki tributary)   (UP_AREA  9,334.5 km2)
// The Ogun's MAIN_BAS (1090023020) is the whole 48,394 km2 Lagos Lagoon system,
// including the Osun basin, so it must NOT be used as the catchment.
// ---------------------------------------------------------------------------
var OUTLETS = {
  ogunMouth: 1090960280,
  lowerMainstem: 1090950490,
  upperOgun: 1090928900,
  oyanDam: 1090931470
};

var lagosSystem = hybas9.filter(ee.Filter.eq('MAIN_BAS', 1090023020));

// HYBAS_IDs of `outletId` and every unit draining into it.
function upstreamIds(outletId) {
  // 150 passes exceeds the longest level-9 flow path in the basin.
  return ee.List(ee.List.sequence(1, 150).iterate(function(_, acc) {
    acc = ee.List(acc);
    var newIds = lagosSystem.filter(ee.Filter.inList('NEXT_DOWN', acc)).aggregate_array('HYBAS_ID');
    return acc.cat(newIds).distinct();
  }, ee.List([outletId])));
}

var idsCatchment = upstreamIds(OUTLETS.ogunMouth);
var idsAboveLower = upstreamIds(OUTLETS.lowerMainstem);
var idsZ1 = upstreamIds(OUTLETS.upperOgun);
var idsZ2 = upstreamIds(OUTLETS.oyanDam);
var idsZ3 = idsAboveLower.removeAll(idsZ1).removeAll(idsZ2);
var idsZ4 = idsCatchment.removeAll(idsAboveLower);

function zoneGeom(ids) {
  return lagosSystem.filter(ee.Filter.inList('HYBAS_ID', ids)).geometry().dissolve();
}

var z1Geom = zoneGeom(idsZ1);
var z2Geom = zoneGeom(idsZ2);
var z3Geom = zoneGeom(idsZ3);
var z4Geom = zoneGeom(idsZ4);
var catchmentGeom = zoneGeom(idsCatchment);

// Sanity check: every catchment unit assigned exactly once.
print('Level-9 units per zone (Z1, Z2, Z3, Z4):',
  idsZ1.size(), idsZ2.size(), idsZ3.size(), idsZ4.size());
print('Total Ogun catchment units (must equal the sum above):', idsCatchment.size());
print('Catchment upstream area km2 (expect 22,165.7):',
  lagosSystem.filter(ee.Filter.eq('HYBAS_ID', OUTLETS.ogunMouth)).first().get('UP_AREA'));

var estuaryRawBox = ee.Geometry.Polygon([
  [[3.32, 6.45], [3.51, 6.45], [3.51, 6.58], [3.32, 6.58], [3.32, 6.45]]
]);
var estuaryGeom = estuaryRawBox.difference(catchmentGeom, 30);

var SCRIPT_VERSION = '2.5.0';
var EXPORT_UTC = ee.Date(Date.now()).format('YYYY-MM-dd\'T\'HH:mm:ss\'Z\'', 'UTC');

function makeUnitFeature(geom, id, order, name, unitType, regime, color, summary, management) {
  var areaKm2 = geom.area(100).divide(1e6);
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
    z1Geom, 'Z1', 1, 'Upper Ogun Headwaters Sub-Basin', 'Hydrological Sub-Basin (hybas_9)',
    'Basement Runoff Core', '#0284C7',
    'Upper Ogun mainstem and headwaters upstream of the Oyan confluence (HydroBASINS L9 upstream tracing). Basement-complex terrain where shallow soils and steeper slopes generate seasonal infiltration-excess overland flow.',
    'Maintain upland gallery forest buffers and contour soil-conservation practices along headwater tributaries.'
  ),
  makeUnitFeature(
    z2Geom, 'Z2', 2, 'Oyan-Ofiki Tributary Sub-Basin', 'Hydrological Sub-Basin (hybas_9)',
    'Regulated Tributary Sub-Basin', '#0D9488',
    'Oyan and Ofiki tributary basin upstream of the Oyan Dam outlet, regulated by the Oyan Reservoir.',
    'Integrate telemetric stage monitoring with reservoir operating records where gauge data are available.'
  ),
  makeUnitFeature(
    z3Geom, 'Z3', 3, 'Middle Ogun Mainstem Sub-Basin', 'Hydrological Sub-Basin (hybas_9)',
    'Mainstem Fluvial Corridor', '#D97706',
    'Mainstem reach from the Oyan confluence past Abeokuta to about 6.9 N, across the basement-to-sedimentary transition.',
    'Preserve non-buildable fluvial setback corridors and monitor bank stability along braided mainstem reaches.'
  ),
  makeUnitFeature(
    z4Geom, 'Z4', 4, 'Lower Ogun Alluvial Corridor', 'Hydrological Sub-Basin (hybas_9)',
    'Low-Gradient Alluvial Floodplain', '#DC2626',
    'Lowest Ogun reaches and side tributaries between about 6.9 N and the Lagos Lagoon, a low-gradient alluvial floodplain prone to seasonal ponding.',
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
// 2 km riparian corridor as a raster distance mask (a vector buffer of the whole
// river network exceeds Earth Engine's memory limit).
var riparianMask = ogunRivers.distance(2000).lte(2000);

Map.centerObject(fullStudyGeom, 8);
Map.addLayer(analyticalUnits, {}, 'Audited Hydrological & Estuarine Units');
Map.addLayer(ogunRivers, {color: '#0284C7'}, 'HydroSHEDS River Network (Order >= 3)');


var startDateStr = '2019-01-01';
// filterDate end is exclusive: use the first day after the study period.
var endDateStr = '2025-01-01';
var glo30 = ee.ImageCollection('COPERNICUS/DEM/GLO30_2024_1').select('DEM');
// mosaic() drops the native 30 m projection (it defaults to a 1-degree grid), which
// made ee.Terrain.slope return no data and silently zeroed the slope mask and the
// SAR inundation proxy. Restore the native projection before computing slope.
var dem = glo30.filterBounds(fullStudyGeom).mosaic()
  .setDefaultProjection(glo30.first().projection())
  .clip(fullStudyGeom);
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
// Limited to the Oyan-Ofiki zone (Z2) so the Ogun mainstem channel is excluded.
var oyanReservoirMask = jrcMaxExtent.eq(1).clip(oyanBox.intersection(z2Geom, 30));
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
  // ASCENDING: the descending track covers only ~5% of the Ogun catchment
  // (0% of Z1 and Z2); the ascending track covers all units every month.
  .filter(ee.Filter.eq('orbitProperties_pass', 'ASCENDING'))
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

var s1Peak2022Passes = s1Collection
  .filterDate('2022-09-01', '2022-11-01')
  .map(function(img) { return img.focal_median(50, 'circle', 'meters'); });

// --- SAR flood detection --------------------------------------------------
// A fixed VV < -16.5 dB threshold alone is dominated by dry-season false alarms
// (burnt savanna and dry ground in Z1/Z2 darken in Jan-Mar). A pixel is counted
// as flooded only if it is dark, at least 3 dB darker than its dry-season
// (Jan-Mar, 2019-2024) reference, on gentle slopes, outside permanent water and
// less than 15 m above the nearest drainage (MERIT Hydro HAND).
var s1DryReference = s1Collection.filter(ee.Filter.calendarRange(1, 3, 'month'))
  .median().focal_median(50, 'circle', 'meters');
var handMask = ee.Image('MERIT/Hydro/v1_0_1').select('hnd').lt(15);

function floodMask(vvImg) {
  return vvImg.lt(-16.5)
    .and(vvImg.subtract(s1DryReference).lt(-3))
    .and(lowSlopeMask)
    .and(seasonalDomainMask)
    .and(handMask);
}

// Optical cross-check, not independent validation: Google Dynamic World (Sentinel-2) pixels labelled
// water (0) or flooded vegetation (3), outside permanent water and < 15 m above drainage.
var dwLabels = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1').select('label')
  .filterBounds(fullStudyGeom).filterDate(startDateStr, endDateStr);
var maskedDwTemplate = ee.Image.constant(0).toFloat().rename('label').updateMask(0);

// The catchment flood series is measured over the lower-Ogun floodplain
// (Z3 + Z4) only; Z1/Z2 values remain affected by dry-season artefacts.
var floodplainGeom = z3Geom.union(z4Geom, 30);

// Per-pass detection: the fraction of Sep-Oct 2022 passes in which each pixel was
// flooded, times its area, is the mean flooded area over the period.
var sarPeakProxyKm2 = s1Peak2022Passes.map(function(img) { return floodMask(img).toFloat(); }).mean()
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

  var climateSlopeStats = meanAnnualRain.addBands([meanShallowSm, slope]).reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: geom,
    scale: 100,
    maxPixels: 1e10,
    tileScale: 16
  });

  var waterStats = s2MultiYear.select('ndti').reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: geom,
    scale: 30,
    maxPixels: 1e10,
    tileScale: 16
  });

  var riparianStats = s2MultiYear.select('ndvi').updateMask(riparianMask).reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: geom,
    scale: 30,
    maxPixels: 1e10,
    tileScale: 16
  });

  var inundationSum = sarPeakProxyKm2.addBands(permanentWaterKm2).reduceRegion({
    reducer: ee.Reducer.sum(),
    geometry: geom,
    scale: 60,
    maxPixels: 1e10,
    tileScale: 16
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

// Fully masked float placeholders, used only when a month has no images, so an
// empty month yields null instead of an error. They are never merged with real
// images (mixing their type with real bands fails in Earth Engine).
var maskedChirpsTemplate = ee.Image.constant(0).toFloat().rename('precipitation').updateMask(0);
var maskedEra5Template = ee.Image.constant(0).toFloat().rename('volumetric_soil_water_layer_1').updateMask(0);
var maskedS1Template = ee.Image.constant(0).toFloat().rename('VV').updateMask(0);
var maskedS2Template = ee.Image.constant([0, 0]).toFloat().rename(['ndti', 'ndvi']).updateMask(0);

function orTemplate(col, template) {
  return ee.ImageCollection(ee.Algorithms.If(col.size().gt(0), col, ee.ImageCollection([template])));
}

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
  var dwMonth = dwLabels.filterDate(mStart, mEnd);

  // Per-pass flood masks (1 flooded, 0 not, masked outside each pass's footprint).
  var s1FloodPasses = s1Month.map(function(img) { return floodMask(img).toFloat().rename('VV'); });
  var floodFraction = orTemplate(s1FloodPasses, maskedS1Template).mean();
  var floodEver = orTemplate(s1FloodPasses, maskedS1Template).max();
  var dwWetFraction = orTemplate(dwMonth.map(function(img) {
    return img.eq(0).or(img.eq(3)).toFloat().rename('label');
  }), maskedDwTemplate).mean().updateMask(seasonalDomainMask.and(handMask));

  var s1MedImg = orTemplate(s1Month, maskedS1Template).median();
  var s2MedImg = orTemplate(s2Month, maskedS2Template).median();

  return {
    yearMonth: mStart.format('YYYY-MM'),
    pentadCount: chirpsMonth.size(),
    era5Count: era5Month.size(),
    s1Count: s1Month.size(),
    s2SceneCount: s2Month.size(),
    rainImg: orTemplate(chirpsMonth, maskedChirpsTemplate).sum(),
    smImg: orTemplate(era5Month, maskedEra5Template).mean(),
    dwCount: dwMonth.size(),
    // Mean flooded area: per-pixel fraction of passes flooded x pixel area.
    sarAreaImg: floodFraction.multiply(ee.Image.pixelArea()).divide(1e6).rename('VV'),
    // Maximum extent: area flooded in at least one pass of the month.
    sarMaxImg: floodEver.multiply(ee.Image.pixelArea()).divide(1e6).rename('VV'),
    dwAreaImg: dwWetFraction.multiply(ee.Image.pixelArea()).divide(1e6).rename('VV'),
    reservoirAreaImg: s1MedImg.lt(-16.5)
      .and(oyanReservoirMask)
      .multiply(ee.Image.pixelArea())
      .divide(1e6)
      .rename('VV'),
    ndtiImg: s2MedImg.select('ndti').updateMask(openEstuaryWaterMask)
  };
}

function reduceMean(img, band, geom, scale) {
  return img.reduceRegion({reducer: ee.Reducer.mean(), geometry: geom, scale: scale, maxPixels: 1e9, tileScale: 4}).get(band);
}

function reduceSum(img, geom, scale) {
  return img.reduceRegion({reducer: ee.Reducer.sum(), geometry: geom, scale: scale, maxPixels: 1e9, tileScale: 4}).get('VV');
}

function ndtiStats(mi, geom) {
  var px = ee.Number(mi.ndtiImg.reduceRegion({
    reducer: ee.Reducer.count(), geometry: geom, scale: 30, maxPixels: 1e9, tileScale: 4
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
    'sar_flood_km2': ee.Algorithms.If(mi.s1Count.gt(0), reduceSum(mi.sarAreaImg, floodplainGeom, 120), null),
    'sar_flood_max_km2': ee.Algorithms.If(mi.s1Count.gt(0), reduceSum(mi.sarMaxImg, floodplainGeom, 120), null),
    'dw_flood_km2': ee.Algorithms.If(mi.dwCount.gt(0), reduceSum(mi.dwAreaImg, floodplainGeom, 60), null),
    'dw_images': mi.dwCount,
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
      'sar_flood_max_km2': ee.Algorithms.If(isEstuary, null, ee.Algorithms.If(mi.s1Count.gt(0), reduceSum(mi.sarMaxImg, geom, 120), null)),
      'dw_flood_km2': ee.Algorithms.If(isEstuary, null, ee.Algorithms.If(mi.dwCount.gt(0), reduceSum(mi.dwAreaImg, geom, 60), null)),
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

// --- Map context layers (for the website map) --------------------------------
// River network inside the catchment (Strahler order >= 3), simplified for the web.
var riverNetwork = ogunRivers
  .filterBounds(catchmentGeom)
  .map(function(f) {
    return ee.Feature(f.geometry().intersection(catchmentGeom, 100).simplify(150), {
      'ORD_STRA': f.get('ORD_STRA')
    });
  });

Export.table.toDrive({
  collection: riverNetwork,
  description: 'ogun_rivers',
  fileFormat: 'GeoJSON'
});

// Oyan Reservoir outline: the largest JRC maximum-extent water body in the reservoir domain.
var reservoirPolys = oyanReservoirMask.selfMask().reduceToVectors({
  geometry: oyanBox.intersection(z2Geom, 30),
  scale: 30,
  geometryType: 'polygon',
  eightConnected: true,
  maxPixels: 1e9
}).map(function(f) { return f.set('area_km2', f.geometry().area(30).divide(1e6)); });

var reservoirOutline = ee.FeatureCollection([
  ee.Feature(reservoirPolys.sort('area_km2', false).first()).simplify(60)
    .set('name', 'Oyan Reservoir (JRC maximum water extent)')
]);

Export.table.toDrive({
  collection: reservoirOutline,
  description: 'oyan_reservoir',
  fileFormat: 'GeoJSON'
});
