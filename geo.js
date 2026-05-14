// Mapping from "By" tow-company strings (as they appear in our scraped data)
// to the company's known yard location in Boston. Used to approximate
// where each car was towed from, since the source has no per-car coordinates.
//
// Addresses pulled from boston.gov/departments/transportation/towing-companies-boston.
// Coordinates are hand-lookup at the listed address; not perfect but close.
//
// BTD is the city's own street-cleaning operation — those tows happen anywhere
// in Boston, so we scatter them across BOSTON_NEIGHBORHOODS deterministically
// by plate hash rather than pinning them at the BTD lot.

window.COMPANY_LOCATIONS = {
  // name in our "By" data : { lat, lon, area, fullName, address }
  "Todisco Towing":   {lat:42.3699,lon:-71.0382,area:"East Boston",fullName:"Todisco Towing",address:"East Boston / Roxbury yards"},
  "D and G":          {lat:42.3536,lon:-71.1359,area:"Allston",fullName:"D & G Towing",address:"2 Emery Rd, Allston, MA 02134"},
  "Stanleys":         {lat:42.2960,lon:-71.1135,area:"Jamaica Plain",fullName:"Stanley's Towing",address:"3430 Washington St, Jamaica Plain, MA 02130"},
  "D and D":          {lat:42.3325,lon:-71.0524,area:"South Boston",fullName:"D & D Towing",address:"1 Ellery St, South Boston, MA 02127"},
  "A and B":          {lat:42.3083,lon:-71.0568,area:"Dorchester",fullName:"A & B Towing",address:"150 B Freeport St, Dorchester, MA 02122"},
  "Walsh":            {lat:42.3331,lon:-71.0699,area:"South Boston",fullName:"Walsh Towing",address:"255 Southampton St, South Boston, MA 02118"},
  "Roberts Towing":   {lat:42.3450,lon:-71.1456,area:"Brighton",fullName:"Roberts Towing",address:"25 Goodenough St, Brighton, MA 02135"},
  "Brighton":         {lat:42.3590,lon:-71.1342,area:"Allston",fullName:"Brighton Towing",address:"100 Hano St, Allston, MA 02134"},
  "Akiki and Sons":   {lat:42.2566,lon:-71.1230,area:"Hyde Park",fullName:"Akiki Towing",address:"97 Providence St, Hyde Park, MA 02136"},
  "Anytime Tow":      {lat:42.2783,lon:-71.1180,area:"Hyde Park",fullName:"Anytime Towing",address:"750 Hyde Park Ave, Boston, MA 02136"},
  "East Coast":       {lat:42.3315,lon:-71.0680,area:"Newmarket",fullName:"Eastcoast Towing",address:"46 Newmarket Sq, Boston, MA 02118"},
  "Auto Service and Tire": {lat:42.2716,lon:-71.0905,area:"Mattapan",fullName:"Auto Service & Tire",address:"1590 Blue Hill Ave, Mattapan, MA 02126"},
  "Peters":           {lat:42.3083,lon:-71.0568,area:"Dorchester",fullName:"Peter's Towing",address:"150 Freeport St, Dorchester, MA 02122"},
  "JMAC":             {lat:42.3601,lon:-71.0589,area:"Boston",fullName:"JMAC Towing",address:"Boston, MA"},
  "Always Open":      {lat:42.2843,lon:-71.0926,area:"Mattapan",fullName:"Always Open Towing",address:"18 Talbot Ave, Mattapan, MA 02124"},
  "Quealy Towing":    {lat:42.3601,lon:-71.0589,area:"Boston",fullName:"Quealy Towing",address:"Boston, MA"},
  "Ahlquist":         {lat:42.3601,lon:-71.0589,area:"Boston",fullName:"Ahlquist Towing",address:"Boston, MA"},
  "LaPierre":         {lat:42.3601,lon:-71.0589,area:"Boston",fullName:"LaPierre Towing",address:"Boston, MA"},
  "Parkway":          {lat:42.2569,lon:-71.1268,area:"Hyde Park",fullName:"Parkway Towing",address:"1 Westinghouse Plaza, Hyde Park, MA 02136"},
  "Tri State Recovery":{lat:42.3601,lon:-71.0589,area:"Boston",fullName:"Tri-State Recovery",address:"Boston, MA"},
  "Milans Towing":    {lat:42.3601,lon:-71.0589,area:"Boston",fullName:"Milan's Towing",address:"Boston, MA"},
  "Cityside":         {lat:42.3814,lon:-71.0680,area:"Charlestown",fullName:"Cityside Towing",address:"6 Roland St, Charlestown, MA 02129"},
  "N.E.A.B":          {lat:42.3601,lon:-71.0589,area:"Boston",fullName:"N.E.A.B Towing",address:"Boston, MA"},
  "Metro":            {lat:42.2780,lon:-71.1175,area:"Hyde Park",fullName:"Metro Towing",address:"749 Hyde Park Ave, Boston, MA 02136"},
};

window.BTD_IMPOUND = {
  fullName: "City of Boston — BTD Tow Lot",
  address: "200 Frontage Rd, Boston, MA 02118",
  lat: 42.3358, lon: -71.0635,
};

// Used to scatter BTD (city street-cleaning) tows since they occur city-wide.
window.BOSTON_NEIGHBORHOODS = [
  [42.3539, -71.1337, "Allston"],
  [42.3503, -71.0810, "Back Bay"],
  [42.3588, -71.0707, "Beacon Hill"],
  [42.3464, -71.1627, "Brighton"],
  [42.3782, -71.0602, "Charlestown"],
  [42.2987, -71.0613, "Dorchester"],
  [42.3699, -71.0382, "East Boston"],
  [42.3429, -71.1003, "Fenway"],
  [42.2552, -71.1245, "Hyde Park"],
  [42.3097, -71.1151, "Jamaica Plain"],
  [42.2774, -71.0926, "Mattapan"],
  [42.3299, -71.1052, "Mission Hill"],
  [42.2840, -71.1268, "Roslindale"],
  [42.3308, -71.0894, "Roxbury"],
  [42.3358, -71.0500, "South Boston"],
  [42.3387, -71.0816, "South End"],
  [42.2799, -71.1573, "West Roxbury"],
  [42.3601, -71.0589, "Downtown"],
];

// Stable string hash so the same plate always lands at the same scattered point.
window.hashStr = function(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
};

// Given a tow record, return [lat, lon, areaLabel] for where to place its pin.
// We deterministically jitter so multiple tows from the same company spread out
// instead of stacking, but the same plate always lands at the same place.
window.pinFor = function(rec) {
  const key = rec.plate + "|" + rec.time;
  const h = window.hashStr(key);
  // Two pseudo-random offsets in [-1, 1] from the hash.
  const dx = ((h & 0xffff) / 0xffff) * 2 - 1;
  const dy = (((h >>> 16) & 0xffff) / 0xffff) * 2 - 1;

  let base, area;
  if (rec.by === "BTD" || rec.agency === "BTD") {
    const n = window.BOSTON_NEIGHBORHOODS;
    const pick = n[h % n.length];
    return [pick[0] + dx * 0.005, pick[1] + dy * 0.007, pick[2]];
  }
  const loc = window.COMPANY_LOCATIONS[rec.by];
  if (!loc) {
    return [42.3601 + dx * 0.01, -71.0589 + dy * 0.013, "Boston"];
  }
  return [loc.lat + dx * 0.0025, loc.lon + dy * 0.0035, loc.area];
};

// Where the car was taken (impound destination).
window.impoundFor = function(rec) {
  if (rec.by === "BTD" || rec.agency === "BTD") return window.BTD_IMPOUND;
  const loc = window.COMPANY_LOCATIONS[rec.by];
  if (loc) {
    return {fullName: loc.fullName, address: loc.address, lat: loc.lat, lon: loc.lon};
  }
  return {fullName: "Unknown lot", address: "Boston, MA",
          lat: 42.3601, lon: -71.0589};
};

// Make → 2-letter initials, like "Honda" → "HO".
window.makeInitials = function(make) {
  if (!make) return "??";
  const word = make.trim().split(/\s+/)[0].toUpperCase();
  return (word + "??").slice(0, 2);
};

// Stable per-make color so all Hondas look the same on the map.
const PALETTE = [
  "#8e8e93", // gray (most common, like rodinrooh)
  "#0a84ff", // blue
  "#ff9f0a", // orange
  "#30d158", // green
  "#bf5af2", // purple
  "#ff453a", // red
  "#5e5ce6", // indigo
  "#64d2ff", // teal
  "#ffd60a", // yellow
];
window.colorForMake = function(make) {
  const init = window.makeInitials(make);
  if (init === "??") return "#aeaeb2";
  return PALETTE[window.hashStr(init) % PALETTE.length];
};
