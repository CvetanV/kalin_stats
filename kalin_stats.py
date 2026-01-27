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
                date = st.date_input("Date", value=st.session_state.selected_date)
                time = st.time_input("Time", value=st.session_state.selected_time)
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
                # Update session state for persistence
                st.session_state.selected_date = date
                st.session_state.selected_time = time
                
                # Calculate total feeding
                total_feed = f_formula + f_breast + f_bottle
                
                # Combine date and time (localized to Brussels)
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

            # View Toggle
            view_mode = st.radio("View Mode", ["Raw Historical Data", "Daily Aggregations"], horizontal=True)

            if view_mode == "Raw Historical Data":
                # Metrics to filter
                numerical_metrics = [
                    'weight', 'height', 'head_size', 'temperature', 
                    'feed_formula', 'feed_breast', 'feed_bottle', 'feed_total'
                ]
                
                col_f1, col_f2 = st.columns([3, 1])
                with col_f1:
                    selected_metrics = st.multiselect(
                        "Select numerical metrics to display",
                        options=numerical_metrics,
                        default=['weight', 'feed_total']
                    )
                with col_f2:
                    show_diapers = st.checkbox("Show Diaper Changes", value=True)

                if selected_metrics:
                    # Prepare data for plotting
                    melted_df = df.melt(id_vars=['timestamp'], value_vars=selected_metrics, 
                                       var_name='Metric', value_name='Value')
                    
                    # Remove null values for the graph
                    melted_df = melted_df.dropna(subset=['Value'])

                    fig = px.line(melted_df, x='timestamp', y='Value', color='Metric',
                                 title="Kalin's Metrics Over Time (Raw Logs)",
                                 markers=True,
                                 template="plotly_dark")
                    
                    fig.update_layout(xaxis_title="Time", yaxis_title="Value")
                    st.plotly_chart(fig, use_container_width=True)
                
                if show_diapers:
                    st.write("**Diaper Changes Timeline**")
                    diaper_df_raw = df[df['diaper_type'].notnull()]
                    if not diaper_df_raw.empty:
                        fig_diaper_raw = px.scatter(diaper_df_raw, x='timestamp', y='diaper_type', 
                                                   color='diaper_type', title="Diaper Changes (Raw Events)",
                                                   labels={'diaper_type': 'Type'},
                                                   template="plotly_dark", height=300)
                        st.plotly_chart(fig_diaper_raw, use_container_width=True)
                    else:
                        st.info("No diaper data recorded yet.")
                
                if not selected_metrics and not show_diapers:
                    st.info("Please select at least one metric or show diapers to visualize.")

            else:
                # Daily Aggregations logic
                st.subheader("Daily Insights")
                
                col_agg1, col_agg2 = st.columns(2)
                
                with col_agg1:
                    # Feeding Aggregations
                    st.write("**Feeding Patterns**")
                    daily_feed = df.groupby('date').agg({
                        'feed_formula': 'sum',
                        'feed_breast': 'sum',
                        'feed_bottle': 'sum',
                        'feed_total': 'sum',
                        'id': 'count' # Frequency
                    }).reset_index().rename(columns={'id': 'frequency'})
                    
                    # Ensure numeric types for Plotly wide-form
                    feed_cols = ['feed_formula', 'feed_breast', 'feed_bottle', 'feed_total']
                    daily_feed[feed_cols] = daily_feed[feed_cols].fillna(0).astype(float)
                    
                    # Feed Volume Chart
                    fig_vol = px.bar(daily_feed, x='date', y=['feed_formula', 'feed_breast', 'feed_bottle'],
                                    title="Daily Feeding Volume (ml)",
                                    labels={'value': 'Volume (ml)', 'variable': 'Type'},
                                    barmode='stack',
                                    template="plotly_dark")
                    st.plotly_chart(fig_vol, use_container_width=True)
                    
                    # Feed Frequency Chart
                    fig_freq = px.line(daily_feed, x='date', y='frequency',
                                      title="Daily Feeding Frequency (Counts)",
                                      markers=True,
                                      template="plotly_dark")
                    st.plotly_chart(fig_freq, use_container_width=True)

                with col_agg2:
                    # Diaper Aggregations
                    st.write("**Diaper Patterns**")
                    # Pivot diaper types to get daily counts
                    diaper_df = df[df['diaper_type'].notnull()].copy()
                    if not diaper_df.empty:
                        daily_diaper = diaper_df.groupby(['date', 'diaper_type']).size().unstack(fill_value=0).reset_index()
                        
                        # Ensure all categories exist and are float for Plotly
                        d_types = ["Wet", "Mixed", "Dry"]
                        for d_type in d_types:
                            if d_type not in daily_diaper.columns:
                                daily_diaper[d_type] = 0
                            daily_diaper[d_type] = daily_diaper[d_type].astype(float)
                        
                        fig_diaper = px.bar(daily_diaper, x='date', y=d_types,
                                           title="Daily Diaper Counts",
                                           labels={'value': 'Count', 'variable': 'Type'},
                                           barmode='stack',
                                           template="plotly_dark")
                        st.plotly_chart(fig_diaper, use_container_width=True)
                        
                        # Show total diaper count trend
                        daily_diaper['Total'] = daily_diaper[d_types].sum(axis=1)
                        fig_diaper_total = px.line(daily_diaper, x='date', y='Total',
                                                 title="Total Daily Diapers",
                                                 markers=True,
                                                 template="plotly_dark")
                        st.plotly_chart(fig_diaper_total, use_container_width=True)
                    else:
                        st.info("No diaper data recorded yet for aggregation.")

            # Show Recent Logs (Always shown at bottom)
            st.write("---")
            st.subheader("Recent Logs")
            st.dataframe(df.sort_values('timestamp', ascending=False), use_container_width=True)

        else:
            st.info("No data found. Go to 'Enter Data' to add your first logs.")

if __name__ == "__main__":
    main()
