import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import pytz
import plotly.express as px

# --- Configuration ---
BRUSSELS_TZ = pytz.timezone('Europe/Brussels')

def get_now_brussels():
    return datetime.now(BRUSSELS_TZ)


# --- Database Setup ---
DB_URL = "postgresql+psycopg2://neondb_owner:npg_XH3bh0KCqDzn@ep-frosty-pond-a91rmd9d-pooler.gwc.azure.neon.tech/neondb?sslmode=require"
engine = create_engine(DB_URL)
Base = declarative_base()

class KalinMetric(Base):
    __tablename__ = 'kalin_metrics'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime(timezone=True), nullable=False) 
    weight = Column(Float)
    height = Column(Float)
    head_size = Column(Float)
    temperature = Column(Float)
    diaper_type = Column(String(50)) # Wet, Mixed, Dry
    feed_formula = Column(Float)
    feed_breast = Column(Float)
    feed_bottle = Column(Float)
    feed_total = Column(Float)

# Create the table
Base.metadata.create_all(engine)

def main():
    st.set_page_config(page_title="Kalin's Growth & Metrics", layout="wide")
    st.title("👶 Kalin's Growth & Metrics Tracker")

    # Initialize Session State for Date and Time
    now = get_now_brussels()
    if 'selected_date' not in st.session_state:
        st.session_state.selected_date = now.date()
    if 'selected_time' not in st.session_state:
        st.session_state.selected_time = now.time()

    # Navigation using Tabs at the top
    tab_enter, tab_trends = st.tabs(["📝 Enter Data", "📈 View Trends"])

    with tab_enter:
        st.header("New Measurements")
        with st.form("metrics_form", clear_on_submit=False):
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("General Metrics")
                # Using keys directly binds widgets to session state
                date = st.date_input("Date", key="selected_date")
                time = st.time_input("Time", key="selected_time")
                weight = st.number_input("Weight (kg)", min_value=0.0, step=0.01, format="%.2f", value=0.0)
                height = st.number_input("Height (cm)", min_value=0.0, step=0.1, format="%.1f", value=0.0)
                head_size = st.number_input("Head Size (cm)", min_value=0.0, step=0.1, format="%.1f", value=0.0)
                temp = st.number_input("Temperature (°C)", min_value=0.0, step=0.1, format="%.1f", value=0.0)
            
            with col2:
                st.subheader("Feeding & Diaper")
                diaper = st.selectbox("Diaper Change", ["N/A", "Wet", "Mixed", "Dry"])
                st.write("---")
                st.write("**Feeding Volumes (ml)**")
                f_formula = st.number_input("Formula", min_value=0.0, step=5.0, value=0.0)
                f_breast = st.number_input("Breast", min_value=0.0, step=5.0, value=0.0)
                f_bottle = st.number_input("Bottle", min_value=0.0, step=5.0, value=0.0)

            submit = st.form_submit_button("Save Metrics")

            if submit:
                # Calculate total feeding
                total_feed = f_formula + f_breast + f_bottle
                
                # Combine date and time (using the values from widgets tied to state)
                dt_localized = BRUSSELS_TZ.localize(datetime.combine(date, time))
                # Normalize to UTC for storage
                dt_utc = dt_localized.astimezone(pytz.utc)
                
                # Create session
                Session = sessionmaker(bind=engine)
                session = Session()
                
                try:
                    new_metric = KalinMetric(
                        timestamp=dt_utc,
                        weight=weight if weight > 0 else None,
                        height=height if height > 0 else None,
                        head_size=head_size if head_size > 0 else None,
                        temperature=temp if temp > 0 else None,
                        diaper_type=diaper if diaper != "N/A" else None,
                        feed_formula=f_formula if f_formula > 0 else None,
                        feed_breast=f_breast if f_breast > 0 else None,
                        feed_bottle=f_bottle if f_bottle > 0 else None,
                        feed_total=total_feed if total_feed > 0 else None
                    )
                    session.add(new_metric)
                    session.commit()
                    st.success(f"Metrics saved! (Time: {dt_localized.strftime('%H:%M')} Brussels)")
                except Exception as e:
                    st.error(f"Error saving data: {e}")
                finally:
                    session.close()

    with tab_trends:
        st.header("Growth & Activity Trends")
        
        # Load data
        query = "SELECT * FROM kalin_metrics ORDER BY timestamp ASC"
        df = pd.read_sql(query, engine)

        if not df.empty:
            # Robust conversion to Brussels Time
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            if df['timestamp'].dt.tz is None:
                df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')
            df['timestamp'] = df['timestamp'].dt.tz_convert(BRUSSELS_TZ)
            df['date'] = df['timestamp'].dt.date

            # --- Filter & Aggregation UI ---
            st.subheader("Filters & View Options")
            col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
            
            with col_f1:
                # Date Range Selector
                min_date = df['date'].min()
                max_date = df['date'].max()
                date_range = st.date_input("Select Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
            
            with col_f2:
                # Granularity Selector
                granularity = st.selectbox("Granularity", ["Daily", "Hourly", "Weekly", "Monthly", "Raw"], index=0)
            
            with col_f3:
                # Metrics to filter
                numerical_metrics = [
                    'weight', 'height', 'head_size', 'temperature', 
                    'feed_formula', 'feed_breast', 'feed_bottle', 'feed_total'
                ]
                selected_metrics = st.multiselect("Metrics to Plot", options=numerical_metrics, default=['feed_total'])

            # Apply Date Range Filter
            if len(date_range) == 2:
                start_date, end_date = date_range
                df_filtered = df[(df['date'] >= start_date) & (df['date'] <= end_date)].copy()
            else:
                df_filtered = df.copy()

            if not df_filtered.empty:
                # --- Aggregation Logic ---
                if granularity != "Raw":
                    resample_map = {
                        "Hourly": "H",
                        "Daily": "D",
                        "Weekly": "W",
                        "Monthly": "ME"
                    }
                    freq = resample_map[granularity]
                    
                    # Columns to aggregate
                    sum_cols = ['feed_formula', 'feed_breast', 'feed_bottle', 'feed_total']
                    mean_cols = ['weight', 'height', 'head_size', 'temperature']
                    
                    # Numerical Resampling
                    df_filtered.set_index('timestamp', inplace=True)
                    df_agg_num = df_filtered[mean_cols].resample(freq).mean()
                    df_agg_sum = df_filtered[sum_cols].resample(freq).sum()
                    
                    # Frequency logic: only count events where feeding actually happened
                    df_feed_events = df_filtered[df_filtered['feed_total'] > 0]
                    df_freq = df_feed_events['id'].resample(freq).count().rename('frequency')
                    
                    # Diaper Resampling
                    # We need to pivot diaper types first
                    diaper_df = df_filtered[df_filtered['diaper_type'].notnull()].copy()
                    if not diaper_df.empty:
                        diaper_pivot = pd.get_dummies(diaper_df['diaper_type']).resample(freq).sum()
                        for d_type in ["Wet", "Mixed", "Dry"]:
                            if d_type not in diaper_pivot.columns:
                                diaper_pivot[d_type] = 0.0
                        diaper_pivot['diaper_total'] = diaper_pivot[["Wet", "Mixed", "Dry"]].sum(axis=1)
                    else:
                        diaper_pivot = pd.DataFrame(index=df_agg_num.index, columns=["Wet", "Mixed", "Dry", "diaper_total"]).fillna(0.0)
                    
                    # Merge all
                    df_plot = pd.concat([df_agg_num, df_agg_sum, df_freq, diaper_pivot], axis=1).reset_index()
                    x_col = 'timestamp'
                else:
                    df_plot = df_filtered.copy()
                    x_col = 'timestamp'

                # --- Visualization ---
                st.write("---")
                
                # Row 1: Numerical Trends & Diaper Patterns
                row1_col1, row1_col2 = st.columns(2)
                
                with row1_col1:
                    if selected_metrics:
                        melted_df = df_plot.melt(id_vars=[x_col], value_vars=selected_metrics, 
                                               var_name='Metric', value_name='Value').dropna(subset=['Value'])
                        fig = px.line(melted_df, x=x_col, y='Value', color='Metric',
                                     title=f"Numerical Trends ({granularity})",
                                     markers=True, template="plotly_dark")
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("Select metrics to see numerical trends.")

                with row1_col2:
                    d_types = ["Wet", "Mixed", "Dry"]
                    if granularity != "Raw":
                        fig_diaper = px.bar(df_plot, x=x_col, y=d_types,
                                           title=f"Diaper Patterns ({granularity})",
                                           labels={'value': 'Count', 'variable': 'Type'},
                                           barmode='stack', template="plotly_dark")
                        st.plotly_chart(fig_diaper, use_container_width=True)
                    else:
                        st.write("**Diaper Events Timeline**")
                        diaper_raw = df_filtered[df_filtered['diaper_type'].notnull()]
                        if not diaper_raw.empty:
                            fig_diaper_raw = px.scatter(diaper_raw, x='timestamp', y='diaper_type', 
                                                       color='diaper_type', title="Diaper Changes (Raw)",
                                                       template="plotly_dark", height=300)
                            st.plotly_chart(fig_diaper_raw, use_container_width=True)
                        else:
                            st.info("No diaper data in this range.")

                # Row 2: Feeding Frequency & Dedicated Weight Trend (Visible when not Raw)
                if granularity != "Raw":
                    row2_col1, row2_col2 = st.columns(2)
                    
                    with row2_col1:
                        fig_freq = px.line(df_plot, x=x_col, y='frequency',
                                          title=f"Feeding Frequency ({granularity})",
                                          markers=True, template="plotly_dark")
                        st.plotly_chart(fig_freq, use_container_width=True)
                    
                    with row2_col2:
                        if 'weight' in df_plot.columns:
                            fig_weight = px.line(df_plot.dropna(subset=['weight']), x=x_col, y='weight',
                                               title=f"Weight Trend ({granularity})",
                                               markers=True, template="plotly_dark",
                                               line_shape='linear', color_discrete_sequence=['#00CC96'])
                            st.plotly_chart(fig_weight, use_container_width=True)

                # Show filtered logs
                st.write("---")
                st.subheader(f"Filtered Logs ({len(df_filtered)} records)")
                # Ensure we sort by timestamp even if it was set as index
                if df_filtered.index.name == 'timestamp':
                    st.dataframe(df_filtered.sort_index(ascending=False), use_container_width=True)
                else:
                    st.dataframe(df_filtered.sort_values('timestamp', ascending=False), use_container_width=True)
            else:
                st.warning("No data found for the selected date range.")

        else:
            st.info("No data found. Go to 'Enter Data' to add your first logs.")

if __name__ == "__main__":
    main()
