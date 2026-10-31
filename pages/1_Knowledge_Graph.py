import streamlit as st
import os
import json
from memory_store import MemoryStore
from pyvis.network import Network
import logging
import tempfile

# --- Page Configuration ---
st.set_page_config(
    page_title="Knowledge Graph",
    layout="wide"
)

st.title("🧠 Interactive Knowledge Graph")

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

# --- Initialization ---
@st.cache_resource
def get_memory_store():
    """Caches the MemoryStore instance."""
    try:
        return MemoryStore()
    except Exception as e:
        logging.error(f"Failed to initialize MemoryStore: {e}")
        return None

memory_store = get_memory_store()
if not memory_store:
    st.error("Fatal: Could not connect to MemoryStore. Please ensure the backend is running correctly.")
    st.stop()

# --- Data Loading and Graph Construction ---
@st.cache_data(ttl=60)
def load_and_build_graph_elements():
    """Loads memories and builds a list of nodes and edges for Pyvis."""
    nodes_data = {}
    edges_data = []
    
    memories = memory_store.get_all_memories()
    if not memories:
        return [], []

    for mem in memories:
        mem_id = mem['id']
        mem_doc = mem.get('document', 'No content')
        
        # Add Memory Node to dictionary to handle duplicates
        nodes_data[mem_id] = {
            'id': mem_id, 
            'label': mem_doc[:40] + '...', 
            'title': mem_doc,
            'shape': 'dot',
            'color': '#00FFFF', # Cyan
            'size': 12,
            'shadow': True
        }

        # Process and Add Entity Nodes and Edges
        entities_str = mem.get('metadata', {}).get('entities', '')
        if entities_str:
            entities_list = [entity.strip() for entity in entities_str.split(',') if entity.strip()]
            for entity_name in entities_list:
                # Add Entity Node to dictionary
                if entity_name not in nodes_data:
                    nodes_data[entity_name] = {
                        'id': entity_name, 
                        'label': entity_name,
                        'title': f"Entity: {entity_name}",
                        'shape': 'box',
                        'color': '#FF8C00', # Orange
                        'size': 15,
                        'shadow': True
                    }
                
                # Add Edge from Memory to Entity
                edges_data.append({
                    'source': mem_id, 
                    'to': entity_name, # Pyvis uses 'to'
                    'color': '#999999'
                })
                
    return list(nodes_data.values()), edges_data

# --- Main Application ---
nodes_list, edges_list = load_and_build_graph_elements()

if not nodes_list:
    st.info("No memories found to build the knowledge graph. Start by adding some memories!")
else:
    st.success(f"Graph loaded with {len(nodes_list)} nodes and {len(edges_list)} edges.")
    
    net = Network(notebook=True, directed=True, cdn_resources='remote', height='800px', width='100%', 
                  bgcolor='#0e1117', font_color='#FFFFFF')

    # Explicitly add nodes and edges
    for node in nodes_list:
        net.add_node(node['id'], label=node['label'], title=node['title'], shape=node['shape'], 
                     color=node['color'], size=node['size'], shadow=node['shadow'])
    
    for edge in edges_list:
        net.add_edge(edge['source'], edge['to'], color=edge['color'])

    # Use a stable, good-looking default physics configuration
    options = {
        "physics": {
            "barnesHut": {
                "gravitationalConstant": -4000,
                "centralGravity": 0.15,
                "springLength": 250,
                "springConstant": 0.04,
                "damping": 0.3,
                "avoidOverlap": 0.6
            },
            "minVelocity": 0.75,
            "solver": "barnesHut"
        },
        "interaction": {
            "navigationButtons": True,
            "tooltipDelay": 200
        }
    }
    net.set_options(json.dumps(options))

    # --- Save and Display Graph ---
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode='w', encoding='utf-8') as fp:
            net.save_graph(fp.name)
            html_file_path = fp.name
        
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        st.components.v1.html(html_content, height=800, scrolling=True)
        
    finally:
        if 'html_file_path' in locals() and os.path.exists(html_file_path):
            os.remove(html_file_path)

st.markdown("---")
st.markdown("""
**How to use:**
- **Explore:** Pan and zoom to navigate the graph.
- **Inspect:** Hover over nodes to see their full content or name.
- **Organize:** Drag nodes around to manually organize clusters.
- **Memories** are shown as <span style="color:#00FFFF">**cyan**</span> dots.
- **Entities** are shown as <span style="color:#FF8C00">**orange**</span> boxes.
""", unsafe_allow_html=True)