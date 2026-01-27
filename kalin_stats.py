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
    timestamp = Column(DateTime, default=lambda: get_now_brussels(), nullable=False)
    weight = Column(Float)
    height = Column(Float)
    head_size = Column(Float)
    temperature = Column(Float)
    diaper_type = Column(String(50)) # Wet, Mixed, Dry
    feeding_amount = Column(Float)
    feeding_type = Column(String(50)) # Formula, Breast, Bottle

# Create the table
Base.metadata.create_all(engine)

def main():
    st.set_page_config(page_title="Kalin's Growth & Metrics", layout="wide")
    st.title("👶 Kalin's Growth & Metrics Tracker")

    # Navigation using Tabs at the top
    tab_enter, tab_trends = st.tabs(["📝 Enter Data", "📈 View Trends"])

    with tab_enter:
        st.header("New Measurements")
        now = get_now_brussels()
        with st.form("metrics_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                date = st.date_input("Date", now.date())
                time = st.time_input("Time", now.time())
                weight = st.number_input("Weight (kg)", min_value=0.0, step=0.01, format="%.2f", value=0.0)
                height = st.number_input("Height (cm)", min_value=0.0, step=0.1, format="%.1f", value=0.0)
                head_size = st.number_input("Head Size (cm)", min_value=0.0, step=0.1, format="%.1f", value=0.0)
            
            with col2:
                temp = st.number_input("Temperature (°C)", min_value=0.0, step=0.1, format="%.1f", value=0.0)
                diaper = st.selectbox("Diaper Change", ["N/A", "Wet", "Mixed", "Dry"])
                feed_amt = st.number_input("Feeding Amount (ml)", min_value=0.0, step=5.0, value=0.0)
                feed_type = st.selectbox("Feeding Type", ["N/A", "Formula", "Breast", "Bottle"])

            submit = st.form_submit_button("Save Metrics")

            if submit:
                # Combine date and time and make it aware of Brussels timezone
                dt = BRUSSELS_TZ.localize(datetime.combine(date, time))
                
                # Create session
                Session = sessionmaker(bind=engine)
                session = Session()
                
                try:
                    new_metric = KalinMetric(
                        timestamp=dt,
                        weight=weight if weight > 0 else None,
                        height=height if height > 0 else None,
                        head_size=head_size if head_size > 0 else None,
                        temperature=temp if temp > 0 else None,
                        diaper_type=diaper if diaper != "N/A" else None,
                        feeding_amount=feed_amt if feed_amt > 0 else None,
                        feeding_type=feed_type if feed_type != "N/A" else None
                    )
                    session.add(new_metric)
                    session.commit()
                    st.success(f"Metrics saved successfully! (Time: {dt.strftime('%H:%M')})")
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
            # Ensure timestamp is datetime and converted to Brussels if needed
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_localize('UTC').dt.tz_convert(BRUSSELS_TZ)
            
            # Metrics to filter
            all_metrics = [
                'weight', 'height', 'head_size', 'temperature', 
                'feeding_amount'
            ]
            
            selected_metrics = st.multiselect(
                "Select metrics to display on the graph",
                options=all_metrics,
                default=all_metrics
            )

            if selected_metrics:
                # Prepare data for plotting
                melted_df = df.melt(id_vars=['timestamp'], value_vars=selected_metrics, 
                                   var_name='Metric', value_name='Value')
                
                # Remove null values for the graph
                melted_df = melted_df.dropna(subset=['Value'])

                fig = px.line(melted_df, x='timestamp', y='Value', color='Metric',
                             title="Kalin's Metrics Over Time",
                             markers=True,
                             template="plotly_dark")
                
                fig.update_layout(xaxis_title="Time", yaxis_title="Value")
                st.plotly_chart(fig, use_container_width=True)
                
                # Show Diaper & Feed Type info if relevant
                st.subheader("Recent Logs")
                st.dataframe(df.sort_values('timestamp', ascending=False), use_container_width=True)
            else:
                st.info("Please select at least one metric to visualize.")
        else:
            st.info("No data found. Go to 'Enter Data' to add your first logs.")

if __name__ == "__main__":
    main()
