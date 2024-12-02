import streamlit as st
import geopandas as gpd
import pandas as pd
import io
import zipfile

st.set_page_config(layout="wide")
st.title("GeoJSON/CSV Data Processor")

# File upload
uploaded_file = st.file_uploader("Upload GeoJSON/CSV file", type=['geojson', 'csv'])

if uploaded_file:
    # Load data
    try:
        if uploaded_file.name.endswith('.geojson'):
            gdf = gpd.read_file(uploaded_file)
        else:
            df = pd.read_csv(uploaded_file)
            geom_col = [col for col in df.columns if 'geom' in col.lower()][0]
            gdf = gpd.GeoDataFrame(df, geometry=gpd.GeoSeries.from_wkt(df[geom_col]))
        
        # Show data preview
        st.write("Data Preview:", gdf.head())
        
        # Create columns for filters
        non_geom_cols = [col for col in gdf.columns if col != 'geometry']
        num_cols = len(non_geom_cols)
        cols = st.columns(num_cols)
        
        # Create filters for each column
        selected_values = {}
        for i, col in enumerate(non_geom_cols):
            with cols[i]:
                unique_vals = sorted(gdf[col].unique().tolist())
                selected_values[col] = st.multiselect(col, unique_vals)
        
        # Apply filters
        filtered_gdf = gdf.copy()
        for col, vals in selected_values.items():
            if vals:  # Only filter if values are selected
                filtered_gdf = filtered_gdf[filtered_gdf[col].isin(vals)]
        
        # Show number of filtered features
        st.write(f"Filtered features: {len(filtered_gdf)}")
        
        # Export functionality
        if len(filtered_gdf) > 0:
            split_col = st.selectbox("Select column to split by:", non_geom_cols)
            
            if st.button("Export"):
                # Create zip file
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w') as zf:
                    for value in filtered_gdf[split_col].unique():
                        subset = filtered_gdf[filtered_gdf[split_col] == value]
                        
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
                        filename = filename.replace('/', '_').replace('\\', '_').replace(' ', '_')
                        
                        zf.writestr(filename, subset.to_json())
                
                # Download button
                st.download_button(
                    "Download GeoJSON files (ZIP)",
                    zip_buffer.getvalue(),
                    "filtered_data.zip",
                    "application/zip"
                )
                
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")