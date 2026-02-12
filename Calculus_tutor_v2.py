# Locate this section in your code and update the 'margin-top' and 'display' properties
st.markdown("""
    <style>
    .status-badge {
        padding: 8px 15px; /* Increase slightly for better vertical centering */
        border-radius: 20px;
        font-size: 14px;
        font-weight: bold;
        display: block; /* Change from inline-block to block */
        border: 1px solid rgba(0,0,0,0.1);
        margin-top: 15px; /* Increase this value to push it down away from the top edge */
        text-align: center;
        width: fit-content;
    }
    
    /* Ensure the column itself doesn't hide the overflow */
    [data-testid="column"] {
        overflow: visible !important;
    }
    </style>
""", unsafe_allow_html=True)
