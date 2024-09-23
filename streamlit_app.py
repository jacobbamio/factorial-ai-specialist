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
import fitz  # PyMuPDF
from paddleocr import PaddleOCR
import re
from io import BytesIO
import os
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
import time

# PaddleOCR configuration
ocr = PaddleOCR(
    use_gpu=False,
    cpu_threads=16,
    use_angle_cls=False,
    lang="es",
    det_db_score_mode="slow",
    rec_algorithm="SVTR_LCNet",
    e2e_pgnet_mode="accurate",
    drop_score=0.5,
)

def login():
    st.markdown(
        """
        <style>
        .login-form {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    with st.form(key='login_form', clear_on_submit=True):
        st.header("Login")
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Login")

        if submit_button:
            if user == st.secrets["streamlit-credentials"]["username"] and pwd == st.secrets["streamlit-credentials"]["password"]:
                st.session_state['logged_in'] = True
                st.success("Logged in successfully!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Invalid username or password")


def extract_text_from_pdf(pdf_file):
    # Open the PDF file using PyMuPDF
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        page_text = page.get_text("text")  # Attempt to extract text from the page
        
        if page_text.strip():  # If text is not empty
            text += page_text
        else:
            # If no selectable text, use OCR
            image = page.get_pixmap()
            image_bytes = image.tobytes("png")
            
            # Perform OCR on the page image
            ocr_result = ocr.ocr(image_bytes)
            page_ocr_text = "\n".join([line[1][0] for line in ocr_result[0]])
            text += page_ocr_text + "\n"
    
    doc.close()
    return text

def gen_pdf(text):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.add_font('DejaVuSans', '', 'resources/fonts/DejaVuSans.ttf', uni=True)
    pdf.set_font('DejaVuSans', '', 12)
    
    pdf.multi_cell(0, 10, text)
    pdf.output("output.pdf")

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

def aai_request(endpoint, api_key, index_name, search_text, top, filter_expression = None):
    search_client = SearchClient(endpoint, index_name, AzureKeyCredential(api_key))
    results = search_client.search(search_text=search_text, top=top, filter = filter_expression)
    return results

def get_trainings_recommendation(selected_name):
    aaisearch_services_credentials = st.secrets["azure-ai-search-services"]
    oai_services_credentials = st.secrets["azure-oai-services"]
    tr_endpoint = oai_services_credentials["TRAININGS_RECOMMENDER_ENDPOINT"]
    tr_api_key = oai_services_credentials["API_KEY"]


    # Step 1. Request the RAG Azure Index the top 2 most similar documents with strengths and weaknesses for the member filter

    filter_expression = f"member eq '{selected_name.lower()}'"

    results = aai_request(endpoint = aaisearch_services_credentials["AZURE_SEARCH_SERVICE_ENDPOINT"], 
                          api_key = aaisearch_services_credentials["AZURE_SEARCH_API_KEY"], 
                          index_name = aaisearch_services_credentials["AZURE_SEARCH_FEEDBACKS_INDEX"],
                          search_text = f"strengths and weaknesses",
                          filter_expression = filter_expression,
                          top = 2)

    # Step 1.1 Get the information ordered for the LLM request
    team_l, name_l, kind_of_l, content_l = [], [], [], [],
    for doc in results:
        team_l.append(doc['team'])
        name_l.append(doc['member'])
        kind_of_l.append(doc['kind_of'])
        content_l.append(doc['content'])

    # Step 2. Send those documents to the LLM
    payload = payloads.keyword_summarizer_payload(team_l, name_l, kind_of_l, content_l)
    keywords_json = json.loads(oai_request(endpoint=tr_endpoint,
                                           api_key=tr_api_key,
                                           payload=payload)["choices"][0]["message"]["content"])
    
    # Step 3. Get the keywords from OpenAI response and search best course fit
    search_keywords = ', '.join(keywords_json["feedback_keywords"].values())
    results = aai_request(endpoint = aaisearch_services_credentials["AZURE_SEARCH_SERVICE_ENDPOINT"], 
                          api_key = aaisearch_services_credentials["AZURE_SEARCH_API_KEY"], 
                          index_name = aaisearch_services_credentials["AZURE_SEARCH_TRAININGS_INDEX"],
                          search_text = search_keywords,
                          top = 5)
    
    best_course_fit = []
    for r in results:
        filtered = {key: r[key] for key in ['title', 'subtitle', 'key_learnings', 'link']}
        best_course_fit.append(filtered)

    # Step 4. Get the response unified for the user
    payload = payloads.training_recommender_payload(keywords_json, best_course_fit)
    keywords_json = json.loads(oai_request(endpoint=tr_endpoint,
                                           api_key=tr_api_key,
                                           payload=payload)["choices"][0]["message"]["content"])

    # Step 5. Return the results
    return keywords_json

def write_job_offer(user_prompt, job_role, include_salary, min_salary, max_salary, currency):
    aaisearch_services_credentials = st.secrets["azure-ai-search-services"]
    oai_services_credentials = st.secrets["azure-oai-services"]
    tr_endpoint = oai_services_credentials["JOB_OFFERS_WRITING_ENDPOINT"]
    tr_api_key = oai_services_credentials["API_KEY"]

    # Step 1. Request the RAG Azure Index the top 2 most similar offers
    results = aai_request(endpoint = aaisearch_services_credentials["AZURE_SEARCH_SERVICE_ENDPOINT"], 
                          api_key = aaisearch_services_credentials["AZURE_SEARCH_API_KEY"], 
                          index_name = aaisearch_services_credentials["AZURE_SEARCH_CAREERS_INDEX"],
                          search_text = f"{job_role}",
                          top = 2)
    
    offer_l, conditions_l = [], []
    for offer in results:
        offer_l.append(offer['offer'])
        conditions_l.append(offer['conditions'])

    # Step 2. Call the LLM to craft a new offer based on the information given
    payload = payloads.job_offer_writing_payload(offer_l, conditions_l, job_role, user_prompt, include_salary, min_salary, max_salary, currency)
    crafted_offer = json.loads(oai_request(endpoint=tr_endpoint,
                                           api_key=tr_api_key,
                                           payload=payload)["choices"][0]["message"]["content"])

    # Step 3. Show the results
    return crafted_offer

st.set_page_config(initial_sidebar_state="collapsed", layout="wide")
pages = ["Feedback Formatter", "Feedback Generator", "Training Recommendation", "Job Offers Writing", "Notion documentation"]
logo_path = "resources/images/factorial_logo.svg"
urls = {"Notion documentation" : "https://factorial-ai-specialist-jacob-bamio.notion.site/Factorial-AI-Specialist-7589768dc24848f38b8eb4728256fa10"}
styles = {
    "nav" : {
        "background-color": "#e51a43",
        "justify-content" : "left"
    },
    "div": {
        "max-width": "32rem",
    },
    "img" : {
        "padding-right" : "50px"
    },
    "span" : {
        "color"   : "#ffffff",
        "padding" : "10px 20px",
        "white-space" : "nowrap",
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

st.markdown(
    """
    <style>
    .streamlit-expanderHeader {
        color: #e51a43;
    }
    .stAlert {
        background-color: #f0f0f0; /* Background color for info */
        border-left: 4px solid #e51a43; /* Custom color for the left border */
    }
    </style>
    """,
    unsafe_allow_html=True
    )

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.warning("Please, log in with your credentials.")
    login()
else:

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

                    ##### Feedback Generator \n

                    Crafts different kind of feedbacks with AI. 360, 1:1, performance review. An all in one tool for testing.

                    ##### BBDDize Feedbacks \n
                    
                    Gets into a database the key phrases and key words of every given feedback, to make it more efficient at the time of recommending trainings.

                    """)


    elif page == "Feedback Formatter":

        if "feedback_formatted_response" not in st.session_state:
            st.session_state.feedback_formatted_response = None

        if "extracted" not in st.session_state:
            st.session_state.extracted = False

        if "feedback_written" not in st.session_state:
            st.session_state.feedback_written = None

        if "previous_file" not in st.session_state:
            st.session_state.previous_file = None

        st.header("Feedback Formatter")
        feedback_file = st.file_uploader("Upload a PDF file with feedback to format", type="pdf", accept_multiple_files=False)

        if feedback_file is not None and feedback_file != st.session_state.previous_file:
            st.session_state.previous_file = feedback_file
            st.session_state.feedback_written = extract_text_from_pdf(feedback_file)
            st.session_state.extracted = True
        elif feedback_file is None:
            st.session_state.extracted = False
            st.session_state.feedback_written = None

        st.session_state.feedback_written = st.text_area("Write down your feedback right here", value=st.session_state.feedback_written or "", height=300, disabled=st.session_state.extracted)

        countries = [country.name for country in pycountry.countries]
        col_left, col_right = st.columns([3, 2])
        selected_country = col_left.selectbox("Choose the country of the person receiving feedback", countries)
        col_right.markdown("<div style='width: 1px; height: 28px'></div>", unsafe_allow_html=True)

        if col_right.button("Format Feedback", use_container_width=True):
            if st.session_state.feedback_written:
                oai_services_credentials = st.secrets["azure-oai-services"]
                payload = payloads.feedback_formatter_payload(culture=selected_country,
                                                            language=detect(st.session_state.feedback_written),
                                                            initial_feedback=st.session_state.feedback_written)
                with st.spinner("Formatting feedback..."):
                    st.session_state.feedback_formatted_response = json.loads(oai_request(endpoint=oai_services_credentials["FEEDBACK_FORMATTER_ENDPOINT"],
                                                                                          api_key=oai_services_credentials["API_KEY"],
                                                                                          payload=payload)["choices"][0]["message"]["content"])

        st.subheader("Feedback Formatted")

        ff_col_left, ff_col_right = st.columns(2)

        if st.session_state.feedback_formatted_response is not None:
            
            try:
                # Get the dict information inside the response.json()
                feedback_formatted = st.session_state.feedback_formatted_response["feedback_formatted"]
                feedback_analysis = st.session_state.feedback_formatted_response["feedback_analysis"]
                short_tip = st.session_state.feedback_formatted_response["short_tip"]
                top_well_done = st.session_state.feedback_formatted_response["top_well_done"]
                top_improvers = st.session_state.feedback_formatted_response["top_improvers"]

                ff_col_left.subheader("AI Generated Feedback")
                ff_col_left.write(feedback_formatted)
                binary_pdf = gen_pdf(feedback_formatted)

                ff_col_left.write(f"A short tip: {short_tip}")
                
                with open("output.pdf", "rb") as file:
                    btn=ff_col_left.download_button(
                    label="Generate PDF with the AI improved feedback!",
                    data=file,
                    file_name="feedback.pdf",
                    mime="application/pdf"
                )
                
                ff_col_right.subheader("AI Analysis about your feedback")
                ff_col_right.info(feedback_analysis)
                placeholder_warning = ff_col_right.empty()
                col1, col2, col3 = ff_col_right.columns(3)

                if len(top_well_done) == 0:
                    placeholder_warning.warning(f"The feedback didn't adapt properly to the culture of {selected_country}. Try improving:")
                    for i, col in enumerate([col1, col2, col3]):
                        if i < len(top_improvers):
                            col.error(top_improvers[i])
                else:
                    for i, col in enumerate([col1, col2, col3]):
                        if i < len(top_well_done):
                            col.success(top_well_done[i])
                        if i < len(top_improvers):
                            col.warning(top_improvers[i])
            except:
                st.warning("An error ocurred during the request. Please try again.")

    elif page == "Training Recommendation":

        st.header("Training Recommendation")
        st.write("In this tab, you will have to choose one of the members in our team, and based in their feedback database, our AI is going to recommend the best training fit for him.")
        teams = {
            "Direction Team": [
                {"title": "Engineering Director", "name": "Ayaan"},
                {"title": "Product Director", "name": "Mei-Ling"},
                {"title": "Design Director", "name": "Santiago"}
            ],
            "Generic Resources Team": [
                {"title": "Data Analytics Engineer", "name": "Amara"},
                {"title": "AI Engineer", "name": "Sven"}
            ],
            "Recruitment Squad": [
                {"title": "Product Manager", "name": "Hana"},
                {"title": "Engineering Manager", "name": "Luca"},
                {"title": "Backend Engineer", "name": "Priya"},
                {"title": "Frontend Engineer", "name": "Yuki"},
                {"title": "Designer", "name": "Omar"}
            ],
            "Performance Squad": [
                {"title": "Product Manager", "name": "Tatiana"},
                {"title": "Engineering Manager", "name": "Thiago"},
                {"title": "Backend Engineer", "name": "Aisling"},
                {"title": "Frontend Engineer", "name": "Dimitri"},
                {"title": "Designer", "name": "Fatima"}
            ],
            "Engagement Squad": [
                {"title": "Product Manager", "name": "Anders"},
                {"title": "Engineering Manager", "name": "Leila"},
                {"title": "Backend Engineer", "name": "Pavel"},
                {"title": "Frontend Engineer", "name": "Ines"},
                {"title": "Designer", "name": "Aksel"}
            ]
        }

        selected_team = st.selectbox("Choose a team", list(teams.keys()))
        team_members = teams[selected_team]

        st.markdown("""
        <style>
        .stButton > button {
            height: 150px;
            width: 250px;
            font-size: 20px;
            text-align: center;
            line-height: 30px;
        }
        </style>
        """, unsafe_allow_html=True)

        cols = st.columns(5)
        selected_name = None

        for i, member in enumerate(team_members):
            if cols[i].button(f"## **{member['title']}**\n\n{member['name']}"):
                selected_name = member["name"]
                with st.spinner(f"Analyzing {selected_name}'s received feedback..."):
                    training_recommendations = get_trainings_recommendation(selected_name)

        if selected_name:
            try:
                st.subheader(f"Training recommendations for {selected_name}")
                st.info(training_recommendations["analysis"])
                st.info(training_recommendations["link_1"])
                st.info(training_recommendations["link_2"])
                st.info(training_recommendations["link_3"])
            except:
                st.warning("Something went wrong. Please try again in a few seconds.")
        else:
            st.subheader("Select a team member to see their training recommendation.")

    elif page == "Job Offers Writing":

        st.header("Job Offers Writing")
        st.write("In this tab, our AI will craft a job offer, based on previous offers from Factorial. The recruiters, will just have to include the role, and, if they want to, set some constraints.")
        import streamlit as st

        col1, col2, col3, col4, col5 = st.columns(5)
        include_salary = col1.checkbox("Include Salary?")
        job_role = col2.text_input("Job role")
        min_salary = col3.number_input("Minimum Salary", min_value=0, step=1000, disabled = not include_salary, value = 15000)
        max_salary = col4.number_input("Maximum Salary", min_value=0, step=1000, disabled = not include_salary, value = 30000)
        currency = col5.selectbox("Currency", ["EUR", "USD", "GBP", "CAD", "AUD"], disabled = not include_salary)

        user_prompt = st.text_area(label = "Introduce some extra guidance for the AI!", height = 250,
                                   placeholder = "This offer shouldn't have any emoji (even being a little dull if you ask me), and include the following links:")
        
        crafted_offer = None

        if st.button("Write the offer!", use_container_width=True):
            with st.spinner("Crafting a brand new offer with AI..."):
                crafted_offer = write_job_offer(user_prompt, job_role, include_salary, min_salary, max_salary, currency)

        st.subheader("Job Offer")
        if crafted_offer != None:
            try:
                filtered_conditions = {key: value for key, value in crafted_offer["conditions"].items() if value}
                infos = list(filtered_conditions.values())
                for i in range(0, len(infos), 3):
                    cols = st.columns(3)
                    for idx, value in enumerate(infos[i:i+3]):
                        cols[idx].info(f"{value}")
                
                st.write(crafted_offer["offer"])

            except Exception as e:
                st.warning("Something went wrong. Please, wait a few seconds and try again.")
                st.write(e)

        
    elif page == "Feedback Generator":

        if "feedback_generated_response" not in st.session_state:
            st.session_state.feedback_generated_response = None

        st.header("Generate Feedback with AI")
        st.subheader("Select the kind of feedback you want to craft")

        col_left, col_mid, col_right = st.columns(3)

        feedback_choice = col_left.radio("Feedback choices", ["360 feedback",
                                                              "1 : 1",
                                                              "Performance Review",
                                                              "Self Evaluation",
                                                              "Horizontal Feedback"])
        
        if feedback_choice != "360 feedback":

            mid_left, mid_right = col_mid.columns(2)

            if feedback_choice == "1 : 1":
                giver = mid_left.radio("Who gives the feedback?", ["Manager", "Employee"])
                if giver == "Manager":
                    receiver = mid_right.radio("Who receives the feedback?", ["Employee"])
                else:
                    receiver = mid_right.radio("Who receives the feedback?", ["Manager"])
            elif feedback_choice == "Performance Review":
                giver = mid_left.radio("Who gives the feedback?", ["Manager"])
                receiver = mid_right.radio("Who receives the feedback?", ["Employee"])

            elif feedback_choice == "Self Evaluation" or feedback_choice == "Horizontal Feedback":
                giver = mid_left.radio("Who gives the feedback?", ["Manager", "Employee"])
                if giver == "Manager":
                    receiver = mid_right.radio("Who receives the feedback?", ["Manager"])
                else:
                    receiver = mid_right.radio("Who receives the feedback?", ["Employee"])

            giver_name = mid_left.text_input(label="Name of the one giving feedback", placeholder="Paul")
            receiver_name = mid_right.text_input(label="Name of the one receiving feedback", placeholder="Luca")
            roles = giver + ", " + receiver
            giver_number = 1
            receiver_number = 1 

            custom_prompt = col_right.text_area(label="Introduce an user prompt to specify anything you want something to be said in this feedback",
                                                placeholder="Paul is so happy with Luca",
                                                height=132)

        
        else:

            mid_left, mid_right = col_mid.columns(2)
            receiver_name    = col_left.text_input("Who are receiving the feedback?", placeholder = "Paul, Ariana")
            giver_number    = mid_left.number_input("How many people is giving feedback?", step = 1, max_value = 5)
            receiver_number = mid_right.number_input("How many people is receiving feedback?", step = 1, max_value = 5)
            giver_name = col_mid.text_input(label = "Introduce the names separated by comma, of the people involved",
                                    placeholder = "Paul, Ariana, Luis")
            roles = col_mid.text_input(label = "Introduce the roles separated by comma, of the people involved",
                                    placeholder = "Manager, Developer, Designer")
            
            custom_prompt = col_right.text_area(label = "Introduce an user prompt to specify anything you want something to be said in this feedbacks",
                                                placeholder = "Everyone is so happy with Paul, so the feedback must be good, with just a few constructive things to say",
                                                height=205)
            
        if st.button("Craft feedback with AI", use_container_width=True):

            if custom_prompt:
                oai_services_credentials = st.secrets["azure-oai-services"]
                payload = payloads.feedback_generation(kind_of         = feedback_choice,
                                                    giver_number    = giver_number,
                                                    receiver_number = receiver_number,
                                                    giver_name      = giver_name,
                                                    receiver_name   = receiver_name,
                                                    roles           = roles,
                                                    custom_prompt   = custom_prompt)
                
                with st.spinner("Crafting custom feedback..."):
                    st.session_state.feedback_generated_response = json.loads(oai_request(endpoint=oai_services_credentials["FEEDBACK_GENERATOR_ENDPOINT"],
                                                                                        api_key=oai_services_credentials["API_KEY"],
                                                                                        payload=payload)["choices"][0]["message"]["content"])

        st.subheader("Feedback created")

        try:
            if st.session_state.feedback_generated_response != None:            
                    col1, col2 = st.columns(2)
                    column_switch = True

                    for key, feedback_item in st.session_state.feedback_generated_response.items():
                        if key.startswith("feedback_"):  
                            if column_switch:
                                with col1:
                                    st.subheader(f"From {feedback_item['from']} to {feedback_item['to']}")
                                    st.info(feedback_item['feedback'])
                            else:
                                with col2:
                                    st.subheader(f"From {feedback_item['from']} to {feedback_item['to']}")
                                    st.info(feedback_item['feedback'])

                            column_switch = not column_switch

        except:

            st.warning("An error ocurred during the request. Please try again")