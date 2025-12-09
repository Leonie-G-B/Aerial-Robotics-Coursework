import numpy as np
import rasterio
from rasterio.transform import from_origin

import matplotlib.pyplot as plt


asc_path = "Maps/MontserratDEM.asc"  #cleaned (remove initial comments) filepath
tif_path = "Maps/MontserratDEM.tif"#new file


with open(asc_path, "r") as f:
    header = {}
    for _ in range(6):
        key, val = f.readline().split()
        header[key] = float(val)

    data = np.loadtxt(f)

print("Loaded DEM:", data.shape)

transform = from_origin(
    header["xllcorner"],
    header["yllcorner"] + header["nrows"] * header["cellsize"],
    header["cellsize"],
    header["cellsize"],
)

with rasterio.open(
    tif_path,
    "w",
    driver="GTiff",
    height=int(header["nrows"]),
    width=int(header["ncols"]),
    count=1,
    dtype=data.dtype,
    crs="EPSG:32620",                
    transform=transform,
) as dst:
    dst.write(data, 1)

print("Wrote GeoTIFF →", tif_path)



# now plot the DEM manually 

header_keys = ["ncols", "nrows", "xllcorner", "yllcorner", "cellsize", "NODATA_value"]
header = {}

with open(asc_path, "r") as f:
    # parse header
    for _ in range(6):
        key, val = f.readline().split()
        header[key] = float(val)

    # load DEM data
    data = np.loadtxt(f)

print("DEM shape:", data.shape)
print("Min:", np.nanmin(data))
print("Max:", np.nanmax(data))

# Replace NODATA (-9999) with NaN
data[data == header["NODATA_value"]] = np.nan

# --- Plot DEM ---
plt.figure(figsize=(10, 8))
im = plt.imshow(data, cmap="terrain", origin="upper")
plt.colorbar(im, label="Elevation (m)")
plt.title("Montserrat DEM (raw ASCII view)")
plt.xlabel("Column index")
plt.ylabel("Row index")
plt.show()