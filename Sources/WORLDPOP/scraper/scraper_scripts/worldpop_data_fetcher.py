import os
import json
import time
import requests
import urllib.parse
import csv
from pathlib import Path
from shapely.geometry import shape, mapping, box
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

year="2026"

class WorldPopDataFetcher:
    def __init__(self, base_url="https://api.worldpop.org/v1"):
        self.base_url = base_url
        self.output_dir = Path("/home/aakash/cdl/ids-drr/flood-data-ecosystem-Himachal-Pradesh/Sources/WORLDPOP/data/agesexstructure") / str(year)
        self.output_dir.mkdir(exist_ok=True, parents=True)

    def simplify_geometry(self, geojson, tolerance=0.14):
        feature = geojson['features'][0]
        geom = shape(feature['geometry'])
        simplified = geom.simplify(tolerance)
        feature['geometry'] = mapping(simplified)
        return geojson

    def truncate_coordinates(self, geojson, precision=1.6):
        def _truncate(x): return round(float(x), precision)

        feature = geojson['features'][0]
        coords = feature['geometry']['coordinates']

        if feature['geometry']['type'] == 'Polygon':
            feature['geometry']['coordinates'] = [[[_truncate(x) for x in point]
                                                   for point in ring]
                                                  for ring in coords]
        elif feature['geometry']['type'] == 'MultiPolygon':
            feature['geometry']['coordinates'] = [[[[_truncate(x) for x in point]
                                                  for point in ring]
                                                   for ring in poly]
                                                  for poly in coords]
        return geojson

    def split_geometry(self, geojson, n_splits=4):
        """Split a geometry into n_splits x n_splits grid pieces."""
        feature = geojson['features'][0]
        geom = shape(feature['geometry'])
        minx, miny, maxx, maxy = geom.bounds

        dx = (maxx - minx) / n_splits
        dy = (maxy - miny) / n_splits

        pieces = []
        for i in range(n_splits):
            for j in range(n_splits):
                cell = box(minx + i*dx, miny + j*dy,
                           minx + (i+1)*dx, miny + (j+1)*dy)
                piece = geom.intersection(cell)
                if not piece.is_empty and piece.area > 0:
                    pieces.append(piece)

        return pieces

    def _geometry_to_geojson(self, geom, original_geojson):
        """Wrap a shapely geometry back into the original geojson structure."""
        new_geojson = json.loads(json.dumps(original_geojson))
        new_geojson['features'][0]['geometry'] = mapping(geom)
        return new_geojson

    def fetch_worldpop_data(self, geojson_path, year=year):
        try:
            with open(geojson_path) as f:
                geojson = json.load(f)

            district = Path(geojson_path).stem

            # Apply both simplification and truncation
            geojson = self.simplify_geometry(geojson)
            # geojson = self.truncate_coordinates(geojson)

            # pop_data = self._make_api_call(geojson, "wpgppop", year, district)
            # # print(pop_data)
            # if pop_data:
            #     self._save_population_data(pop_data, district)

            pyramid_data = self._make_api_call(
                geojson, "wpgpas", year, district)

            if pyramid_data == "PAYLOAD_TOO_LARGE":
                logger.warning(f"Splitting {district} into pieces...")
                pyramid_data = self._fetch_split(geojson, year, district)

            if pyramid_data:
                logger.info(
                    f"Pyramid data for district {district} is {pyramid_data}")
                self._save_pyramid_data(pyramid_data, district, year)

        except Exception as e:
            logger.error(f"Error processing {district}: {str(e)}")
            return False
        return True

    def _fetch_split(self, geojson, year, district, n_splits=4, depth=0):
        """Split the geometry and aggregate results from each piece."""
        if depth > 2:
            logger.error(f"Max split depth reached for {district}")
            return None

        pieces = self.split_geometry(geojson, n_splits=n_splits)
        aggregated = {}

        for idx, piece in enumerate(pieces):
            piece_geojson = self._geometry_to_geojson(piece, geojson)
            # More aggressive simplification for split pieces
            piece_geojson = self.simplify_geometry(piece_geojson, tolerance=0.08)
            piece_geojson = self.truncate_coordinates(piece_geojson, precision=2)

            piece_name = f"{district}_part{idx}_d{depth}"
            result = self._make_api_call(piece_geojson, "wpgpas", year, piece_name)

            # If this piece is still too big, recursively split it
            if result == "PAYLOAD_TOO_LARGE":
                logger.warning(f"Recursively splitting {piece_name}...")
                result = self._fetch_split(piece_geojson, year, piece_name, n_splits=2, depth=depth+1)

            if not result or result == "PAYLOAD_TOO_LARGE":
                continue

            for row in result['data']['agesexpyramid']:
                key = (row['class'], row['age'])
                if key not in aggregated:
                    aggregated[key] = {'class': row['class'], 'age': row['age'], 'male': 0, 'female': 0}
                aggregated[key]['male'] += row['male']
                aggregated[key]['female'] += row['female']

        if aggregated:
            return {'data': {'agesexpyramid': list(aggregated.values())}}
        return None

    def _make_api_call(self, geojson, dataset, year, district):
        try:
            geojson = json.dumps(geojson)
            url = f"{self.base_url}/services/stats"
            params = {
                "dataset": dataset,
                "year": year,
                "geojson": geojson,
                "runasync": "false"
            }

            response = requests.get(url, params=params)
            response.raise_for_status()
            logger.info(f"The response is {response.json()}")
            task_id = response.json()["taskid"]

            attempt = 0
            while attempt < 2:
                time.sleep(2)
                status_url = f"{self.base_url}/tasks/{task_id}"
                status_response = requests.get(status_url)
                status_response.raise_for_status()

                result = status_response.json()
                print(f"[{district}] Poll attempt {attempt} result: {result}")  # <-- add this

                if result.get("status") == "finished":
                    logger.info(f"Task info is {result}")
                    return result
                elif result.get("status") == "failed":
                    return None

                attempt += 1
            return None

        except requests.RequestException as e:
            if "413" in str(e):
                logger.error(f"Payload still too large for {district}")
                return "PAYLOAD_TOO_LARGE"
            return None

    def _save_population_data(self, data, district):
        output_file = self.output_dir / f"{district}_population.csv"
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['district', 'total_population'])
            writer.writerow([district, data['data']['total_population']])

    def _save_pyramid_data(self, data, year, district):
        output_file = self.output_dir / f"{district}_{year}.csv"
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(
                f, fieldnames=['class', 'age', 'male', 'female'])
            writer.writeheader()
            for row in data['data']['agesexpyramid']:
                writer.writerow(row)


def main():
    fetcher = WorldPopDataFetcher()
    geojson_dir = Path(
        "/home/aakash/cdl/ids-drr/flood-data-ecosystem-Himachal-Pradesh/Sources/WORLDPOP/scraper/shapefiles/district_geojson")

    for geojson_file in geojson_dir.glob("*.geojson"):
        logger.info(f"Processing {geojson_file.name}")
        fetcher.fetch_worldpop_data(str(geojson_file))


if __name__ == "__main__":
    main()



