import streamlit as st
import geopandas as gpd
import pandas as pd
import json
import io
import zipfile
from datetime import datetime

st.set_page_config(layout="wide")
st.title("GeoJSON/CSV/JSON Data Processor")

def format_column_name(col_name):
    return col_name.replace('_', ' ').title()

def convert_timestamps_in_properties(properties):
    """Convert any timestamps in properties to strings."""
    if isinstance(properties, dict):
        for key, value in properties.items():
            if isinstance(value, (pd.Timestamp, datetime)):
                properties[key] = value.isoformat()
            elif isinstance(value, dict):
                properties[key] = convert_timestamps_in_properties(value)
            elif isinstance(value, list):
                properties[key] = [convert_timestamps_in_properties(item) if isinstance(item, dict) else item for item in value]
    return properties

uploaded_file = st.file_uploader("Upload GeoJSON/CSV/JSON file", type=['geojson', 'csv', 'json'])

if uploaded_file:
    try:
        # Read data based on file type
        if uploaded_file.name.endswith('.geojson'):
            gdf = gpd.read_file(uploaded_file)
        elif uploaded_file.name.endswith('.json'):
            json_data = json.load(uploaded_file)
            
            if isinstance(json_data, dict) and json_data.get('type') == 'FeatureCollection':
                gdf = gpd.read_file(io.StringIO(json.dumps(json_data)))
            else:
                if isinstance(json_data, list):
                    df = pd.DataFrame(json_data)
                else:
                    df = pd.DataFrame([json_data])
                
                geom_col = [col for col in df.columns if 'geom' in col.lower()]
                if geom_col:
                    gdf = gpd.GeoDataFrame(df, geometry=gpd.GeoSeries.from_wkt(df[geom_col[0]]))
                else:
                    st.error("No geometry column found in JSON data")
                    st.stop()
        else:  # CSV file
            df = pd.read_csv(uploaded_file)
            geom_col = [col for col in df.columns if 'geom' in col.lower()][0]
            gdf = gpd.GeoDataFrame(df, geometry=gpd.GeoSeries.from_wkt(df[geom_col]))
        
        # Show data preview in an expandable section
        with st.expander("Data Preview", expanded=False):
            st.dataframe(gdf.head(100))
        
        # Get columns for filtering, excluding geometry and complex objects
        non_geom_cols = [col for col in gdf.columns if col != 'geometry' and 
                        gdf[col].dtype in ['object', 'int64', 'float64', 'bool']]
        
        # Create filter section
        st.subheader("Filter Data")
        
        # Let user select which columns to filter by
        filter_cols = st.multiselect(
            "Select columns to filter by:",
            non_geom_cols,
            key="filter_columns"
        )
        
        # Dictionary to store selected values
        selected_values = {}
        
        # Create filters for selected columns
        if filter_cols:
            # Create two columns for filters
            col1, col2 = st.columns(2)
            half = len(filter_cols) // 2
            
            # First column of filters
            with col1:
                for col in filter_cols[:half]:
                    unique_vals = sorted(gdf[col].dropna().unique().tolist())
                    if len(unique_vals) > 100:
                        selected_values[col] = st.multiselect(
                            format_column_name(col),
                            unique_vals,
                            key=f"filter_{col}",
                            help=f"Type to search among {len(unique_vals)} values"
                        )
                    else:
                        selected_values[col] = st.multiselect(
                            format_column_name(col),
                            unique_vals,
                            key=f"filter_{col}"
                        )
            
            # Second column of filters
            with col2:
                for col in filter_cols[half:]:
                    unique_vals = sorted(gdf[col].dropna().unique().tolist())
                    if len(unique_vals) > 100:
                        selected_values[col] = st.multiselect(
                            format_column_name(col),
                            unique_vals,
                            key=f"filter_{col}_2",
                            help=f"Type to search among {len(unique_vals)} values"
                        )
                    else:
                        selected_values[col] = st.multiselect(
                            format_column_name(col),
                            unique_vals,
                            key=f"filter_{col}_2"
                        )
        
        # Apply filters
        filtered_gdf = gdf.copy()
        for col, vals in selected_values.items():
            if vals:  # Only filter if values are selected
                filtered_gdf = filtered_gdf[filtered_gdf[col].isin(vals)]
        
        # Show number of filtered features
        st.write(f"Filtered features: {len(filtered_gdf)}")
        
        # Export section
        if len(filtered_gdf) > 0:
            st.subheader("Export Data")
            
            # Let user select any column to split by
            split_col = st.selectbox(
                "Select column to split by:",
                non_geom_cols,
                help="Files will be split based on unique values in this column"
            )
            
            if st.button("Export"):
                # Create zip file
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for value in filtered_gdf[split_col].unique():
                        subset = filtered_gdf[filtered_gdf[split_col] == value]
                        
                        # Convert all datetime columns to strings before conversion to GeoJSON
                        subset_copy = subset.copy()
                        for col in subset_copy.select_dtypes(include=['datetime64[ns]']).columns:
                            subset_copy[col] = subset_copy[col].astype(str)
                        
                        # Handle nested timestamps in properties
                        for col in subset_copy.columns:
                            if isinstance(subset_copy[col].iloc[0], dict):
                                subset_copy[col] = subset_copy[col].apply(
                                    lambda x: convert_timestamps_in_properties(x)
                                )
                        
                        # Create filename with filter information
                        filter_info = []
                        for col, vals in selected_values.items():
                            if vals:  # Only include active filters
                                filter_values = '_'.join(str(v) for v in vals)
                                filter_info.append(f"{col}-{filter_values}")
                        
                        # Combine split value with filter info
                        if filter_info:
                            filename = f"{split_col}-{value}__filters__{'-'.join(filter_info)}.geojson"
                        else:
                            filename = f"{split_col}-{value}.geojson"
                            
                        # Clean filename
                        filename = (filename.replace('/', '_')
                                  .replace('\\', '_')
                                  .replace(' ', '_')
                                  .replace('"', '')
                                  .replace("'", ""))
                        
                        # Convert to GeoJSON string
                        geojson_str = subset_copy.to_json()
                        
                        # Write to zip file
                        zf.writestr(filename, geojson_str)
                
                # Download button
                st.download_button(
                    "Download GeoJSON files (ZIP)",
                    zip_buffer.getvalue(),
                    "filtered_data.zip",
                    "application/zip"
                )
                
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")