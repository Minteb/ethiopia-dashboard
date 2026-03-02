# -----------------------------
# ViSTA Project: Ethiopia Geospatial Data Visualization Dashboard
# Individual points, bold region boundaries, layer switching
# -----------------------------

import os
import sys
import pandas as pd
import geopandas as gpd
import folium
from folium import plugins, Element
from dash import Dash, dcc, html, Input, Output, callback, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px

# ---------------------------
# 1. SET UP PATHS (works in script and Jupyter)
# ---------------------------
if 'ipykernel' in sys.modules:
    # In Jupyter notebook, use current working directory
    BASE_DIR = os.getcwd()
else:
    # In a regular Python script, use the script's location
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, 'data')

csv_path = os.path.join(DATA_DIR, 'Maize_Fingerprint_2015_EC_GPS_onlyUpdated.csv')
cleared_shp_path = os.path.join(DATA_DIR, 'MGPS_Cleared_2015.shp')
regions_shp_path = os.path.join(DATA_DIR, 'eth_admin1.shp')

# ---------------------------
# 2. LOAD AND PREPARE GPS DATA
# ---------------------------
df = pd.read_csv(csv_path)

df.rename(columns={
    'Region': 'region',
    'Zone': 'zone',
    'Woreda': 'woreda',
    'Kebele': 'kebele',
    'latitude': 'lat',
    'longitude': 'lon'
}, inplace=True)

df = df[(df['lat'] != 0) & (df['lon'] != 0)]
regions = sorted(df['region'].dropna().unique())

# Cleared GPS shapefile
cleared_gdf = gpd.read_file(cleared_shp_path)

# Handle missing CRS (assume WGS84 if none)
if cleared_gdf.crs is None:
    print("⚠️ Cleared GPS shapefile has no CRS. Assuming EPSG:4326 (WGS84).")
    cleared_gdf.set_crs(epsg=4326, inplace=True)
elif cleared_gdf.crs != 'EPSG:4326':
    cleared_gdf = cleared_gdf.to_crs('EPSG:4326')

# Ensure geometries are points
if cleared_gdf.geometry.iloc[0].geom_type != 'Point':
    cleared_gdf['geometry'] = cleared_gdf.geometry.centroid

# ---------------------------
# 3. LOAD REGION SHAPEFILE
# ---------------------------
regions_gdf = gpd.read_file(regions_shp_path)

# Handle missing CRS for regions
if regions_gdf.crs is None:
    print("⚠️ Region shapefile has no CRS. Assuming EPSG:4326.")
    regions_gdf.set_crs(epsg=4326, inplace=True)
elif regions_gdf.crs != 'EPSG:4326':
    regions_gdf = regions_gdf.to_crs('EPSG:4326')

region_col = 'adm1_name'  # adjust if column name differs
regions_gdf_clean = regions_gdf[['geometry', region_col]].copy()

# ---------------------------
# 4. CUSTOM HOME BUTTON
# ---------------------------
def add_home_button(m):
    home_js = """
    <script>
    var homeBtn = document.createElement('button');
    homeBtn.innerHTML = '🏠 Home';
    homeBtn.style.position = 'absolute';
    homeBtn.style.top = '10px';
    homeBtn.style.left = '50px';
    homeBtn.style.zIndex = '1000';
    homeBtn.style.backgroundColor = 'white';
    homeBtn.style.border = '2px solid grey';
    homeBtn.style.borderRadius = '3px';
    homeBtn.style.padding = '5px 10px';
    homeBtn.style.cursor = 'pointer';
    homeBtn.onclick = function() {
        map.setView([9.0, 38.5], 6);
    };
    document.body.appendChild(homeBtn);
    </script>
    """
    m.get_root().html.add_child(Element(home_js))

# ---------------------------
# 5. FOLIUM MAP FUNCTION – NO CLUSTERING, BOLD BOUNDARIES
# ---------------------------
def generate_map(selected_region=None, selected_zone=None, selected_woreda=None):
    m = folium.Map(location=[9.0, 38.5], zoom_start=6, control_scale=True, tiles=None)
    folium.TileLayer('openstreetmap', name='OpenStreetMap').add_to(m)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite'
    ).add_to(m)

    # Region boundaries – bold
    folium.GeoJson(
        regions_gdf_clean,
        name='Region Boundaries',
        style_function=lambda x: {'fillColor': 'transparent', 'color': 'black', 'weight': 2, 'dashArray': None},
        tooltip=folium.GeoJsonTooltip(fields=[region_col], aliases=['Region:'])
    ).add_to(m)

    # Feature groups for points
    fg_original = folium.FeatureGroup(name='Original GPS').add_to(m)
    fg_cleared = folium.FeatureGroup(name='Cleared GPS').add_to(m)

    # Filter original points
    filtered = df.copy()
    if selected_region and selected_region != 'All':
        filtered = filtered[filtered['region'] == selected_region]
    if selected_zone and selected_zone != 'All':
        filtered = filtered[filtered['zone'] == selected_zone]
    if selected_woreda and selected_woreda != 'All':
        filtered = filtered[filtered['woreda'] == selected_woreda]

    # Add original points (red circles)
    for _, row in filtered.iterrows():
        popup = folium.Popup(
            f"<b>Original GPS</b><br>"
            f"Region: {row['region']}<br>"
            f"Zone: {row['zone']}<br>"
            f"Woreda: {row['woreda']}<br>"
            f"Kebele: {row['kebele']}",
            max_width=300
        )
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=5,
            color='red',
            fill=True,
            fillColor='red',
            fillOpacity=0.8,
            popup=popup
        ).add_to(fg_original)

    # Filter cleared points (if admin columns exist)
    cleared_filtered = cleared_gdf.copy()
    if 'region' in cleared_filtered.columns and selected_region != 'All':
        cleared_filtered = cleared_filtered[cleared_filtered['region'] == selected_region]
    if 'zone' in cleared_filtered.columns and selected_zone != 'All':
        cleared_filtered = cleared_filtered[cleared_filtered['zone'] == selected_zone]
    if 'woreda' in cleared_filtered.columns and selected_woreda != 'All':
        cleared_filtered = cleared_filtered[cleared_filtered['woreda'] == selected_woreda]

    # Add cleared points (green triangles)
    for _, row in cleared_filtered.iterrows():
        popup_text = f"<b>Cleared GPS</b><br>"
        if 'region' in cleared_filtered.columns:
            popup_text += f"Region: {row['region']}<br>"
        if 'zone' in cleared_filtered.columns:
            popup_text += f"Zone: {row['zone']}<br>"
        if 'woreda' in cleared_filtered.columns:
            popup_text += f"Woreda: {row['woreda']}<br>"
        popup = folium.Popup(popup_text, max_width=300)

        folium.RegularPolygonMarker(
            location=[row.geometry.y, row.geometry.x],
            number_of_sides=3,
            radius=6,
            color='green',
            fill=True,
            fillColor='green',
            fillOpacity=0.9,
            popup=popup
        ).add_to(fg_cleared)

    # Legend
    legend_html = '''
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; background-color: white; padding: 10px; border: 2px solid grey; border-radius: 5px; font-size: 14px;">
        <p><span style="background-color: red; width: 20px; height: 20px; display: inline-block; margin-right: 5px;"></span> Original GPS</p>
        <p><span style="background-color: green; width: 20px; height: 20px; display: inline-block; margin-right: 5px;"></span> Cleared GPS</p>
    </div>
    '''
    m.get_root().html.add_child(Element(legend_html))

    folium.LayerControl().add_to(m)
    plugins.Fullscreen().add_to(m)
    add_home_button(m)

    return m._repr_html_()

# ---------------------------
# 6. DASH APP LAYOUT
# ---------------------------
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server   # <-- IMPORTANT for Render

app.layout = dbc.Container([
    html.H1("ViSTA Project: Ethiopia Geospatial Data Visualization Dashboard", className="text-center mt-4 mb-4"),

    dbc.Row([
        dbc.Col([html.Label("Select Region"),
                 dcc.Dropdown(id='region-dropdown',
                              options=[{'label': 'All', 'value': 'All'}] + [{'label': r, 'value': r} for r in regions],
                              value='All', clearable=False)
                 ], width=4),
        dbc.Col([html.Label("Select Zone"),
                 dcc.Dropdown(id='zone-dropdown', options=[], value='All', clearable=False)
                 ], width=4),
        dbc.Col([html.Label("Select Woreda"),
                 dcc.Dropdown(id='woreda-dropdown', options=[], value='All', clearable=False)
                 ], width=4)
    ], className="mb-3"),

    # Statistics cards
    dbc.Row([
        dbc.Col([dbc.Card(dbc.CardBody([
            html.H5("Total GPS Points", className="card-title"),
            html.H2(id='total-points', children="0", className="card-text text-primary")
        ]), color="light", className="text-center")], width=4),

        dbc.Col([dbc.Card(dbc.CardBody([
            html.H5("Total Cleared Points", className="card-title"),
            html.H2(id='total-cleared', children="0", className="card-text text-success")
        ]), color="light", className="text-center")], width=4),

        dbc.Col([dbc.Card(dbc.CardBody([
            html.H5("Bad Points (Original - Cleared)", className="card-title"),
            html.H2(id='total-bad', children="0", className="card-text text-danger")
        ]), color="light", className="text-center")], width=4)
    ], className="mb-4"),

    dbc.Row([
        dbc.Col([dash_table.DataTable(id='region-table',
                                     columns=[
                                         {"name": "Region", "id": "region"},
                                         {"name": "Original Points", "id": "original"},
                                         {"name": "Cleared Points", "id": "cleared"},
                                         {"name": "Bad Points", "id": "bad"}
                                     ],
                                     style_table={'overflowX': 'auto'},
                                     style_cell={'textAlign': 'left', 'padding': '5px'},
                                     style_header={'fontWeight': 'bold'}
                                     )
                 ])
    ], className="mb-4"),

    dbc.Row([
        dbc.Col([dcc.Graph(id='bar-chart')], width=6),
        dbc.Col([dcc.Graph(id='pie-chart')], width=6)
    ], className="mb-4"),

    dbc.Row([dbc.Col([html.Iframe(id='map', width='100%', height='600')], width=12)]),

    html.Hr(),
    html.Footer("Developed By: Mintesnot Berhanu | Minteb11@gmail.com", className="text-center text-muted")
], fluid=True)

# ---------------------------
# 7. CALLBACKS (unchanged)
# ---------------------------
@callback(
    Output('zone-dropdown', 'options'),
    Output('zone-dropdown', 'value'),
    Input('region-dropdown', 'value')
)
def set_zone_options(selected_region):
    if selected_region == 'All':
        zones = ['All'] + sorted(df['zone'].dropna().unique())
    else:
        zones = ['All'] + sorted(df[df['region'] == selected_region]['zone'].dropna().unique())
    return [{'label': z, 'value': z} for z in zones], 'All'

@callback(
    Output('woreda-dropdown', 'options'),
    Output('woreda-dropdown', 'value'),
    Input('region-dropdown', 'value'),
    Input('zone-dropdown', 'value')
)
def set_woreda_options(selected_region, selected_zone):
    filtered = df.copy()
    if selected_region != 'All':
        filtered = filtered[filtered['region'] == selected_region]
    if selected_zone != 'All':
        filtered = filtered[filtered['zone'] == selected_zone]
    woredas = ['All'] + sorted(filtered['woreda'].dropna().unique())
    return [{'label': w, 'value': w} for w in woredas], 'All'

@callback(
    Output('total-points', 'children'),
    Output('total-cleared', 'children'),
    Output('total-bad', 'children'),
    Output('region-table', 'data'),
    Output('bar-chart', 'figure'),
    Output('pie-chart', 'figure'),
    Input('region-dropdown', 'value'),
    Input('zone-dropdown', 'value'),
    Input('woreda-dropdown', 'value')
)
def update_stats(selected_region, selected_zone, selected_woreda):
    filtered = df.copy()
    if selected_region != 'All':
        filtered = filtered[filtered['region'] == selected_region]
    if selected_zone != 'All':
        filtered = filtered[filtered['zone'] == selected_zone]
    if selected_woreda != 'All':
        filtered = filtered[filtered['woreda'] == selected_woreda]

    total = len(filtered)

    cleared_filtered = cleared_gdf.copy()
    if selected_region != 'All' and 'region' in cleared_filtered.columns:
        cleared_filtered = cleared_filtered[cleared_filtered['region'] == selected_region]
    if selected_zone != 'All' and 'zone' in cleared_filtered.columns:
        cleared_filtered = cleared_filtered[cleared_filtered['zone'] == selected_zone]
    if selected_woreda != 'All' and 'woreda' in cleared_filtered.columns:
        cleared_filtered = cleared_filtered[cleared_filtered['woreda'] == selected_woreda]

    total_cleared = len(cleared_filtered)
    total_bad = total - total_cleared

    region_data = []
    for r in filtered['region'].unique():
        orig_count = len(filtered[filtered['region'] == r])
        if 'region' in cleared_filtered.columns:
            clear_count = len(cleared_filtered[cleared_filtered['region'] == r])
        else:
            clear_count = 0
        region_data.append({
            'region': r,
            'original': orig_count,
            'cleared': clear_count,
            'bad': orig_count - clear_count
        })

    if selected_woreda == 'All':
        bar_counts = filtered['woreda'].value_counts().head(10).reset_index()
        bar_counts.columns = ['woreda', 'count']
        bar_fig = px.bar(bar_counts, x='woreda', y='count', title='Top 10 Woredas by Points',
                         color_discrete_sequence=['#636EFA'])
    else:
        bar_counts = filtered['kebele'].value_counts().head(10).reset_index()
        bar_counts.columns = ['kebele', 'count']
        bar_fig = px.bar(bar_counts, x='kebele', y='count', title='Top 10 Kebeles by Points',
                         color_discrete_sequence=['#636EFA'])

    if selected_zone == 'All':
        pie_counts = filtered['zone'].value_counts().reset_index()
        pie_counts.columns = ['zone', 'count']
        if len(pie_counts) > 10:
            top10 = pie_counts.iloc[:10].copy()
            others = pd.DataFrame({'zone': ['Others'], 'count': [pie_counts.iloc[10:]['count'].sum()]})
            pie_counts = pd.concat([top10, others], ignore_index=True)
        pie_fig = px.pie(pie_counts, values='count', names='zone', title='Zone Distribution (Top 10)',
                         color_discrete_sequence=px.colors.qualitative.Set3)
    else:
        pie_counts = filtered['kebele'].value_counts().reset_index()
        pie_counts.columns = ['kebele', 'count']
        if len(pie_counts) > 10:
            top10 = pie_counts.iloc[:10].copy()
            others = pd.DataFrame({'kebele': ['Others'], 'count': [pie_counts.iloc[10:]['count'].sum()]})
            pie_counts = pd.concat([top10, others], ignore_index=True)
        pie_fig = px.pie(pie_counts, values='count', names='kebele', title='Kebele Distribution (Top 10)',
                         color_discrete_sequence=px.colors.qualitative.Set3)

    return total, total_cleared, total_bad, region_data, bar_fig, pie_fig

@callback(
    Output('map', 'srcDoc'),
    Input('region-dropdown', 'value'),
    Input('zone-dropdown', 'value'),
    Input('woreda-dropdown', 'value')
)
def update_map(selected_region, selected_zone, selected_woreda):
    try:
        return generate_map(selected_region, selected_zone, selected_woreda)
    except Exception as e:
        print("❌ Map error:", e)
        import traceback
        traceback.print_exc()
        m = folium.Map(location=[9.0, 38.5], zoom_start=6)
        folium.Marker([9.0, 38.5], popup=f"Error: {e}", icon=folium.Icon(color='red')).add_to(m)
        return m._repr_html_()

# ---------------------------
# 8. RUN APP
# ---------------------------
if __name__ == '__main__':
    app.run(debug=True)