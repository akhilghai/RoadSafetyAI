import streamlit as st

# Set page config FIRST
st.set_page_config(
    page_title="ROAD SAFETY AI",
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="expanded"
)

from pymongo import MongoClient
from PIL import Image
import pillow_heif
import piexif
import pandas as pd
import pydeck as pdk

# Register HEIC support
pillow_heif.register_heif_opener()

# --- Custom CSS for styling ---
st.markdown("""
    <style>
        .main {background-color: #f5f5f5;}
        h1, h2 {color: #2B3467;}
        .sidebar .sidebar-content {background-color: #2B3467; color: white;}
        .stButton>button {background-color: #EB455F; color: white; border-radius: 5px;}
        .stDownloadButton>button {background-color: #2B3467; color: white;}
        .css-1vq4p4l {padding: 1rem;}
        .css-1vq4p4l:hover {background-color: #EB455F20;}
        .css-1vq4p4l:focus {box-shadow: 0 0 0 0.2rem rgba(235,69,95,.5);}
        .st-emotion-cache-1v0mbdj {background: #f5f6fa;}
        .st-emotion-cache-10trblm {font-size: 2.2rem;}
        .st-emotion-cache-1c7y2kd {color: #EB455F;}
    </style>
""", unsafe_allow_html=True)

# --- MongoDB connection ---
MONGO_URI = "mongodb+srv://akhilghai95:akhilghai95@cluster-roadsafetyai.2jwx5hq.mongodb.net/?retryWrites=true&w=majority&appName=Cluster-RoadSafetyAI"
client = MongoClient(MONGO_URI, ssl=True)
db = client["roadSafetyAIDB"]
users_collection = db["users"]

# --- Remove duplicates and ensure unique index ---
def remove_duplicate_users():
    pipeline = [
        {"$group": {
            "_id": "$username",
            "dups": {"$push": "$_id"},
            "count": {"$sum": 1}
        }},
        {"$match": {"count": {"$gt": 1}}}
    ]
    try:
        duplicates = list(users_collection.aggregate(pipeline))
        for doc in duplicates:
            if doc["dups"]:
                users_collection.delete_many({"_id": {"$in": doc["dups"][1:]}})
    except Exception as e:
        st.error(f"Error removing duplicates: {e}")

remove_duplicate_users()
try:
    users_collection.create_index("username", unique=True)
except Exception as e:
    st.error(f"Index creation failed: {e}")
    st.stop()
try:
    users_collection.update_one(
        {"username": "Kashika"},
        {"$setOnInsert": {"password": "Dobby"}},
        upsert=True
    )
except Exception as e:
    st.error(f"User insertion failed: {e}")

# --- Helper functions ---
def check_login(username, password):
    user = users_collection.find_one({"username": username, "password": password})
    return user is not None

def convert_to_degrees(value):
    d, m, s = value
    return d[0]/d[1] + m[0]/(m[1]*60) + s[0]/(s[1]*3600)

def extract_exif_info(image_file, filename):
    try:
        img = Image.open(image_file)
        exif_bytes = img.info.get("exif")
        width, height = img.size

        info = {
            "FileName": filename,
            "Width": width,
            "Height": height,
            "DateTime": "-",
            "Make": "-",
            "Model": "-",
            "Software": "-",
            "Latitude": None,
            "Longitude": None
        }

        if not exif_bytes:
            return info

        exif_dict = piexif.load(exif_bytes)
        zeroth = exif_dict.get("0th", {})
        info["DateTime"] = zeroth.get(piexif.ImageIFD.DateTime, b'').decode("utf-8", errors='ignore')
        info["Make"] = zeroth.get(piexif.ImageIFD.Make, b'').decode("utf-8", errors='ignore')
        info["Model"] = zeroth.get(piexif.ImageIFD.Model, b'').decode("utf-8", errors='ignore')
        info["Software"] = zeroth.get(piexif.ImageIFD.Software, b'').decode("utf-8", errors='ignore')

        gps = exif_dict.get("GPS", {})
        lat = gps.get(piexif.GPSIFD.GPSLatitude)
        lat_ref = gps.get(piexif.GPSIFD.GPSLatitudeRef, b'').decode("utf-8", errors='ignore')
        lon = gps.get(piexif.GPSIFD.GPSLongitude)
        lon_ref = gps.get(piexif.GPSIFD.GPSLongitudeRef, b'').decode("utf-8", errors='ignore')

        if lat and lon:
            lat_decimal = convert_to_degrees(lat)
            if lat_ref == "S":
                lat_decimal = -lat_decimal
            lon_decimal = convert_to_degrees(lon)
            if lon_ref == "W":
                lon_decimal = -lon_decimal
            info["Latitude"] = lat_decimal
            info["Longitude"] = lon_decimal

        return info

    except Exception as e:
        st.warning(f"Error processing {filename}: {e}")
        return None

# --- Session state ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

# --- Sidebar ---
with st.sidebar:
    st.markdown(
        "<h2 style='color:#EB455F;text-align:center;'>🛣️ ROAD AI</h2>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<div style='text-align:center;font-size:1.2rem;'>Image & Geolocation Dashboard</div>",
        unsafe_allow_html=True
    )
    st.markdown("---")
    if not st.session_state.logged_in:
        st.subheader("🔑 Login")
        username = st.text_input("Username", key="sidebar_username")
        password = st.text_input("Password", type="password", key="sidebar_password")
        if st.button("Sign In", key="sidebar_login"):
            if check_login(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("Invalid credentials")
    else:
        st.success(f"Welcome, {st.session_state.username}!")
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.rerun()
        st.markdown("---")
        st.markdown("### 📌 App Guide")
        st.markdown("""
            1. Upload images (JPG/HEIC)
            2. View EXIF metadata
            3. Explore geolocations on the map
            4. Download data as CSV
        """)

# --- Main content ---
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>ROAD AI</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: #EB455F;'>Road Deteoriation Analysis</h3>", unsafe_allow_html=True)
    st.stop()

st.markdown("## 📸 Image Analyzer")
st.markdown("---")

# --- File Upload Section ---
with st.container():
    uploaded_files = st.file_uploader(
        "Drag & Drop Images Here",
        type=["jpg", "jpeg", "heic"],
        accept_multiple_files=True,
        help="Supported formats: JPG, JPEG, HEIC"
    )

# --- Data Processing & Display ---
if uploaded_files:
    with st.spinner("🔍 Analyzing images..."):
        data = []
        for file in uploaded_files:
            info = extract_exif_info(file, file.name)
            if info:
                data.append(info)
        if data:
            df = pd.DataFrame(data)
            st.success(f"✅ Successfully processed {len(data)} images")

            # --- Data Table ---
            st.markdown("### 📊 EXIF Data Table")
            st.dataframe(
                df.style.highlight_max(axis=0, color="#EB455F30"),
                height=350,
                use_container_width=True
            )

            # --- Geolocation Map (PyDeck) ---
            st.markdown("### 🌍 Geolocation Map")
            geo_df = df.dropna(subset=["Latitude", "Longitude"]).copy()
            geo_df = geo_df[(geo_df["Latitude"].apply(lambda x: isinstance(x, float))) & (geo_df["Longitude"].apply(lambda x: isinstance(x, float)))]
            if not geo_df.empty:
                geo_df["tooltip"] = (
                    "File: " + geo_df["FileName"].astype(str) +
                    "<br>Make: " + geo_df["Make"].astype(str) +
                    "<br>Model: " + geo_df["Model"].astype(str)
                )
                layer = pdk.Layer(
                    "ScatterplotLayer",
                    data=geo_df,
                    get_position='[Longitude, Latitude]',
                    get_color='[235,69,95,160]',
                    get_radius=120,
                    pickable=True,
                    tooltip=True
                )
                view_state = pdk.ViewState(
                    latitude=geo_df["Latitude"].mean(),
                    longitude=geo_df["Longitude"].mean(),
                    zoom=6 if len(geo_df) > 1 else 12,
                    pitch=0
                )
                st.pydeck_chart(
                    pdk.Deck(
                        layers=[layer],
                        initial_view_state=view_state,
                        tooltip={
                            "html": "<b>{FileName}</b><br/>Lat: {Latitude}<br/>Lon: {Longitude}<br/>Make: {Make}<br/>Model: {Model}",
                            "style": {"backgroundColor": "#2B3467", "color": "white"}
                        }
                    )
                )
            else:
                st.info("No valid geolocation data found in the uploaded images.")

            # --- Download Section ---
            st.markdown("---")
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download Full Report (CSV)",
                data=csv,
                file_name="exif_report.csv",
                mime="text/csv",
                help="Download complete EXIF data in CSV format"
            )
        else:
            st.warning("⚠️ No EXIF data extracted from uploaded images")
else:
    st.info("ℹ️ Please upload images to begin analysis")
