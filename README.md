# Reading the Roadside — The Gold Country Markers Catalogue

A public stats page for Dave Dell'Aquila's catalogue of Gold Country
historical markers: **1,305 markers** across eight Mother Lode counties
(El Dorado, Nevada, Placer, Amador, Tuolumne, Calaveras, Mariposa, Sierra),
compiled November 16, 2026 from the Historical Marker Database (HMdb),
cross-checked against the California Office of Historic Preservation.

**Live page:** https://davedellaquila.github.io/gold-country-markers/

- `index.html` is the whole page — headline stats, charts (markers per
  county, the five marker families, state-landmark coverage, and the
  accounted-for completeness bar), a Leaflet map plotting all 1,305
  markers colour-coded by family, the honest gap ledger, and a
  how-it-was-built note. Map tiles and the Leaflet library load from
  their CDNs; everything else is in the one file.
- The catalogue itself (per-county staged JSON with exact coordinates
  and plaque text) is staged for Dave's locations database; this page
  is its public face.
