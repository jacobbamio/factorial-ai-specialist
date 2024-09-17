import os
import streamlit as st
from streamlit.components.v1 import html
from streamlit_navigation_bar import st_navbar
from bs4 import BeautifulSoup, Tag
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pycountry
import payloads
import requests
import json
from langdetect import detect
from fpdf import FPDF

def gen_pdf(text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    pdf.multi_cell(0, 10, text)
    
    return pdf.output(dest='S').encode('latin1')


def oai_request(endpoint, api_key, payload):

    headers = {
        "Content-Type": "application/json",
        "api-key": api_key,
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()  # Will raise an HTTPError if the HTTP request returned an unsuccessful status code
    except requests.RequestException as e:
        raise SystemExit(f"Failed to make the request. Error: {e}")

    return response.json()

st.set_page_config(initial_sidebar_state="collapsed", layout="wide")
pages = ["Feedback Formatter", "Training Recommendation", "Job Offers Writing", "GenAI - Feedbacks" ,"BBDDize Feedbacks", "Notion documentation"]
logo_path = "resources/images/factorial_logo.svg"
urls = {"Notion documentation" : "https://factorial-ai-specialist-jacob-bamio.notion.site/Factorial-AI-Specialist-7589768dc24848f38b8eb4728256fa10"}
styles = {
    "nav" : {
        "background-color": "#e51a43",
        "justify-content" : "left"
    },
    "img" : {
        "padding-right" : "50px"
    },
    "span" : {
        "color"   : "#ffffff",
        "padding" : "10px 20px",
        "white-space" : "nowrap"
    },
    "active" : {
        "color"            : "var(--text-color)",
        "background-color" : "#ffffff",
        "font-weight"      : "normal",
        "padding"          : "10px 20px"
    }
}

page = st_navbar(pages, 
                 logo_path = logo_path, 
                 urls      = urls, 
                 styles    = styles, 
                 options   = True)

if page == "Home":

    st.header("Welcome to the POC Streamlit interface of Factorial AI")
    st.subheader("What's exactly a POC?")
    st.markdown("""
                A POC (Proof Of Concept) is a prototype of a project that aims to:\n
                
                - Verify Feasibility: Confirm that the concept or technology can work as intended in practice.
                - Demonstrate Value: Show the potential benefits or advantages of the concept.
                - Identify Risks and Challenges: Uncover potential issues or obstacles early in the process.
                - Validate Assumptions: Test key assumptions and hypotheses related to the concept.
                
                In this specific case, I have developed some AI tools for HR. You can use each one of them by clicking each one of the header tabs.
                """)
    
    st.subheader("Briefly description of each tab")

    col_left, col_right = st.columns(2)

    col_left.markdown("""

                ##### Feedback Formatter \n

                Adapt given feedback with AI, to make sure it fits a 4A Framework, and the 8 scales of the cultural map.

                ##### Training Recommendation \n

                Provide the right training choices for each employee based on our database of available trainings with AI.
                
                ##### Notion documentation \n

                The easiest to explain! This is a fast shortcut to the in-depth documentation of each feature. \n

                - How was it developed? 
                - What technologies are involved?
                - What's the workflow?
                - Where can I see the code for this feature?

                Every question you have will be outlined right there. And if I left something missing, I'll be there during the technical interview to outline those myself.
                """)

    col_right.markdown("""

                ##### Job Offers Writing \n

                Writes job offers based on context of past offers, making it easier and faster to recruiters to be creative and find the best candidates.

                ##### GenAI - Feedbacks \n

                Crafts different kind of feedbacks with AI. 360, 1:1, performance review. An all in one tool for testing.

                ##### BBDDize Feedbacks \n
                
                Gets into a database the key phrases and key words of every given feedback, to make it more efficient at the time of recommending trainings.

                """)


elif page == "Feedback Formatter":

    if "feedback_formatted_response" not in st.session_state:
        st.session_state.feedback_formatted_response = None
    
    st.header("Feedback Formatter")
    feedback_file = st.file_uploader("Upload a PDF file with feedback to format", type="pdf", accept_multiple_files=False)
    feedback_written = st.text_area("Write down your feedback right here", height=300)

    countries = [country.name for country in pycountry.countries]
    col_left, col_right = st.columns([3,2])
    selected_country = col_left.selectbox("Choose the country of the person receiving feedback", countries)
    col_right.markdown("<div style='width: 1px; height: 28px'></div>", unsafe_allow_html=True)
    
    if col_right.button("Format Feedback", use_container_width=True):

        oai_services_credentials = st.secrets["azure-oai-services"]
        payload = payloads.feedback_formatter_payload(culture = selected_country,
                                                      language = detect(feedback_written),
                                                      initial_feedback = feedback_written)

        st.session_state.feedback_formatted_response = json.loads(oai_request(endpoint = oai_services_credentials["feedback_formatter_endpoint"],
                                                                              api_key = oai_services_credentials["feedback_formatter_api_key"],
                                                                              payload = payload)["choices"][0]["message"]["content"])
        
    st.subheader("Feedback Formatted")

    ff_col_left, ff_col_right = st.columns(2)

    if st.session_state.feedback_formatted_response is not None:
        
        # Get the dict information inside the response.json()
        feedback_formatted = st.session_state.feedback_formatted_response["feedback_formatted"]
        feedback_analysis = st.session_state.feedback_formatted_response["feedback_analysis"]
        short_tip = st.session_state.feedback_formatted_response["short_tip"]
        top_well_done = st.session_state.feedback_formatted_response["top_well_done"]
        top_improvers = st.session_state.feedback_formatted_response["top_improvers"]

        ff_col_left.subheader("AI Generated Feedback")
        ff_col_left.write(feedback_formatted)
        pdf_binario = gen_pdf(feedback_formatted)

        ff_col_left.write(f"A short tip: {short_tip}")
        ff_col_left.download_button(label="Generate PDF with the AI improved feedback!",
                                    data=pdf_binario,
                                    file_name="feedback.pdf",
                                    mime="application/pdf",
                                    use_container_width=True)
        
        ff_col_right.subheader("AI Analysis about your feedback")
        ff_col_right.info(feedback_analysis)
        placeholder_warning = ff_col_right.empty()
        col1, col2, col3 = ff_col_right.columns(3)

        if len(top_well_done) == 0:

            placeholder_warning.warning(f"The feedback didn't adapt properly to the culture of {selected_country}. Try improving:")
            col1.error(top_improvers[0])
            col2.error(top_improvers[1])
            col3.error(top_improvers[2])

        else:
            col1.success(top_well_done[0])
            col1.warning(top_improvers[0])

            col2.success(top_well_done[1])
            col2.warning(top_improvers[1])

            col3.success(top_well_done[2])
            col3.warning(top_improvers[2])



elif page == "Training Recommendation":

    st.header("Training Recommendation")
    st.write("In this tab, you will have to choose one of the members in our team, and based in their feedback database, our AI is going to recommend the best training fit for him.")
    st.markdown("""
    <style>
    .stButton > button {
        height: 150px;
        width: 250px;
        font-size: 20px;
        text-align: center;
        line-height: 30px; /* Vertically center text */
    }
    </style>
    """, unsafe_allow_html=True)

    st.subheader("Direction Team")
    direction_left, direction_mid, direction_right, _, _ = st.columns(5)
    direction_left.button("## **Engineering Director**\n\nAyaan", use_container_width=False)
    direction_mid.button("## **Product Director**\n\nMei-Ling", use_container_width=False)
    direction_right.button("## **Design Director**\n\nSantiago", use_container_width=False)

    st.subheader("Generic Resources Team")
    generic_left, generic_mid, _, _, _ = st.columns(5)
    generic_left.button("## **Data Analytics Engineer**\n\nAmara", use_container_width=False)
    generic_mid.button("## **AI Engineer**\n\nSven", use_container_width=False)

    st.subheader("Recruitment Squad")
    recruitment_left, recruitment_mid1, recruitment_mid2, recruitment_right1, recruitment_right2 = st.columns(5)
    recruitment_left.button("## **Product Manager**\n\nHana", use_container_width=False)
    recruitment_mid1.button("## **Engineering Manager**\n\nLuca", use_container_width=False)
    recruitment_mid2.button("## **Backend Engineer**\n\nPriya", use_container_width=False)
    recruitment_right1.button("## **Frontend Engineer**\n\nYuki", use_container_width=False)
    recruitment_right2.button("## **Designer**\n\nOmar", use_container_width=False)

    st.subheader("Performance Squad")
    performance_left, performance_mid1, performance_mid2, performance_right1, performance_right2 = st.columns(5)
    performance_left.button("## **Product Manager**\n\nTatiana", use_container_width=False)
    performance_mid1.button("## **Engineering Manager**\n\nThiago", use_container_width=False)
    performance_mid2.button("## **Backend Engineer**\n\nAisling", use_container_width=False)
    performance_right1.button("## **Frontend Engineer**\n\nDimitri", use_container_width=False)
    performance_right2.button("## **Designer**\n\nFatima", use_container_width=False)

    st.subheader("Engagement Squad")
    engagement_left, engagement_mid1, engagement_mid2, engagement_right1, engagement_right2 = st.columns(5)
    engagement_left.button("## **Product Manager**\n\nAnders", use_container_width=False)
    engagement_mid1.button("## **Engineering Manager**\n\nLeila", use_container_width=False)
    engagement_mid2.button("## **Backend Engineer**\n\nPavel", use_container_width=False)
    engagement_right1.button("## **Frontend Engineer**\n\nInes", use_container_width=False)
    engagement_right2.button("## **Designer**\n\nAksel", use_container_width=False)

    name = "Amara"

    st.subheader(f"Training recommendations for {name}")

elif page == "Job Offers Writing":

    st.header("Job Offers Writing")
    st.write("In this tab, our AI will craft a job offer, based on previous offers from Factorial. The recruiters, will just have to include the role, and, if they want to, set some constraints.")
    st.text_area(label = "Introduce your prompt to craft a job offer!", height = 250,
                 placeholder = "This offer aims to engage a Senior Backend Engineer")
    st.button("Write the offer!", use_container_width=True)

    st.subheader("Job Offer")
elif page == "GenAI - Feedbacks":

    st.header("Generate Feedback with AI")
    st.subheader("Select the kind of feedback you want to craft")

    col_left, col_mid, col_right = st.columns(3)
    feedback_choice = col_left.radio("Feedback choices", ["360 feedback",
                                                          "1 : 1",
                                                          "Performance Review",
                                                          "Self evaluation",
                                                          "Horizontal Feedback"])
    
    if feedback_choice != "360 feedback":

        giver_index, receiver_index = 0, 0

        mid_left, mid_right = col_mid.columns(2)
        giver = mid_left.radio("Who gives the feedback?", ["Manager", "Employee"], index = giver_index)
        receiver = mid_right.radio("Who receives the feedback?", ["Manager", "Employee"], index = receiver_index)

        if feedback_choice == "Performance Review":
            giver = "Manager"
            receiver = "Employee"
        
        elif feedback_choice == "Self Evaluation":
            if giver == "Manager": receiver = "Manager"
            else: receiver = "Employee"
        mid_left.text_input(label = "Name of the one giving feedback", placeholder = "Paul")
        mid_right.text_input(label = "Name of the one receiving feedback", placeholder = "Luca")

        col_right.text_area(label = "Introduce an user prompt to specify anything you want something to be said in this feedbacks",
                    placeholder = "Paul is so happy with Luca",
                    height = 132)
    
    else:
        col_left.text_input("Who's receiving the feedback?", placeholder = "Paul")
        col_mid.number_input("How many people is giving feedback?", step = 1, max_value = 5)
        col_mid.number_input("How many people is receiving feedback?", step = 1, max_value = 5)
        col_mid.text_input(label = "Introduce the names and roles, separated by comma, of the people involved",
                           placeholder = "Paul Manager, Ariana Developer, Luis Marketing")
        
        col_right.text_area(label = "Introduce an user prompt to specify anything you want something to be said in this feedbacks",
                            placeholder = "Everyone is so happy with Paul, so the feedback must be good, with just a few constructive things to say",
                            height=205)
        
    st.button("Craft feedback with AI", use_container_width=True)
    st.subheader("Feedback created")

elif page == "BBDDize Feedbacks":

    st.header("Upload feedbacks to an Azure Database")
    st.write("""

             The feedbacks given between the people in our teams, is always a text document with a lot of information. This tool will analyze all those documents and get the most relevant information into a database.
             This will help us a lot when we need to match the key phrases in that feedback with training courses in the Training Recommendation tab.

             """)
    
    st.subheader("Choose whose feedback you want to bbdize")
    st.button("Everyone's")

    st.markdown("""
    <style>
    .stButton > button {
        height: 150px;
        width: 250px;
        font-size: 20px;
        text-align: center;
        line-height: 30px; /* Vertically center text */
    }
    </style>
    """, unsafe_allow_html=True)

    st.subheader("Direction Team")
    direction_left, direction_mid, direction_right, _, _ = st.columns(5)
    direction_left.button("## **Engineering Director**\n\nAyaan", use_container_width=False)
    direction_mid.button("## **Product Director**\n\nMei-Ling", use_container_width=False)
    direction_right.button("## **Design Director**\n\nSantiago", use_container_width=False)

    st.subheader("Generic Resources Team")
    generic_left, generic_mid, _, _, _ = st.columns(5)
    generic_left.button("## **Data Analytics Engineer**\n\nAmara", use_container_width=False)
    generic_mid.button("## **AI Engineer**\n\nSven", use_container_width=False)

    st.subheader("Recruitment Squad")
    recruitment_left, recruitment_mid1, recruitment_mid2, recruitment_right1, recruitment_right2 = st.columns(5)
    recruitment_left.button("## **Product Manager**\n\nHana", use_container_width=False)
    recruitment_mid1.button("## **Engineering Manager**\n\nLuca", use_container_width=False)
    recruitment_mid2.button("## **Backend Engineer**\n\nPriya", use_container_width=False)
    recruitment_right1.button("## **Frontend Engineer**\n\nYuki", use_container_width=False)
    recruitment_right2.button("## **Designer**\n\nOmar", use_container_width=False)

    st.subheader("Performance Squad")
    performance_left, performance_mid1, performance_mid2, performance_right1, performance_right2 = st.columns(5)
    performance_left.button("## **Product Manager**\n\nTatiana", use_container_width=False)
    performance_mid1.button("## **Engineering Manager**\n\nThiago", use_container_width=False)
    performance_mid2.button("## **Backend Engineer**\n\nAisling", use_container_width=False)
    performance_right1.button("## **Frontend Engineer**\n\nDimitri", use_container_width=False)
    performance_right2.button("## **Designer**\n\nFatima", use_container_width=False)

    st.subheader("Engagement Squad")
    engagement_left, engagement_mid1, engagement_mid2, engagement_right1, engagement_right2 = st.columns(5)
    engagement_left.button("## **Product Manager**\n\nAnders", use_container_width=False)
    engagement_mid1.button("## **Engineering Manager**\n\nLeila", use_container_width=False)
    engagement_mid2.button("## **Backend Engineer**\n\nPavel", use_container_width=False)
    engagement_right1.button("## **Frontend Engineer**\n\nInes", use_container_width=False)
    engagement_right2.button("## **Designer**\n\nAksel", use_container_width=False)
