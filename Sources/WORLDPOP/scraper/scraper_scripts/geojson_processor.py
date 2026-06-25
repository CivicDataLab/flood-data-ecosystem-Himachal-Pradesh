import json
import os
from copy import deepcopy
from shapely.geometry import MultiPolygon, Polygon, shape, mapping
from shapely.ops import unary_union


def simplify_coordinates(geometry, tolerance=0.08):
    """
    Simplify geometry coordinates using Shpely' simplify method

    Args:
        geometry (_type_): _description_
        tolerance (float, optional): _description_. Defaults to 0.001.
    """
    if geometry['type'] == 'MultiPolygon':
        shapely_geom = shape(geometry)
        simplified = shapely_geom.simplify(tolerance)
        return mapping(simplified)
    return geometry


def convert_multipolygon_to_polygon(feature):
    """Convert Multipolygon to Polygon by taking the largest polygon

    Args:
        feature (_type_): _description_
    """
    geom = feature['geometry']
    if geom['type'] == 'MultiPolygon':
        # Convert to shapely object
        multi_polygon = shape(geom)

        # if it's already a single polygon,return the largest one
        if len(multi_polygon.geoms) == 1:
            return mapping(multi_polygon.geoms[0])
        # find the polygon with largest area
        largest_polygon = max(multi_polygon.geoms, key=lambda x: x.area)
        # convert back to geojson format
        return mapping(largest_polygon)
    return geom


def process_geojson(input_data, output_dir="/home/aakash/cdl/ids-drr/flood-data-ecosystem-Himachal-Pradesh/Sources/WORLDPOP/scraper/shapefiles/district_geojson"):
    """
    Processes GeoJSON files:
    1. Convert MultiPolygon to Polygon
    2. Simplify coordinates
    3. Split into district-wise files


    Args:
        input_data (_type_): _description_
        output_dir (str, optional): _description_. Defaults to "district_geojson".
    """
    os.makedirs(output_dir, exist_ok=True)
    if isinstance(input_data, str):
        with open(input_data, 'r') as f:
            data = json.load(f)
    else:
        data = input_data

    # Process each feature
    for feature in data['features']:
        # Create a copy of the feature
        district_feature = deepcopy(feature)

        # Convert MultiPolygon to Polygon
        district_feature['geometry'] = convert_multipolygon_to_polygon(
            district_feature)

        # Simplify coordinates
        district_feature['geometry'] = simplify_coordinates(
            district_feature['geometry'])

        # Create district-wise GeoJSON
        district_geojson = {
            "type": "FeatureCollection",
            "features": [district_feature]
        }

        # Create safe filename from district name
        district_name = feature['properties']['object_id']
        safe_filename = "".join(x for x in district_name if x.isalnum() or x in [
                                ' ', '_','-']).replace(' ', '_')

        # Save to file
        output_file = os.path.join(output_dir, f"{safe_filename}.geojson")
        with open(output_file, 'w') as f:
            json.dump(district_geojson, f, indent=2)


def main():
    try:
        process_geojson(
            '/home/aakash/cdl/ids-drr/flood-data-ecosystem-Himachal-Pradesh/Maps/hp_tehsil_final.geojson')
        print("Successully processed GeoJSON files!")

    except Exception as e:
        print(f"Error processing GeoJSON: {str(e)}")


if __name__ == "__main__":
    main()
