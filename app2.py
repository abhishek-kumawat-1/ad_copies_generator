import streamlit as st
import pandas as pd
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from serpapi import GoogleSearch
from langchain_openai import AzureChatOpenAI
import secrets

def map_locations_ids_to_resource_names(client, location_ids):
    build_resource_name = client.get_service("GeoTargetConstantService").geo_target_constant_path
    return [build_resource_name(location_id) for location_id in location_ids]

def get_keyword_ideas_with_themes(client, customer_id, location_ids, language_id, base_keywords):
    keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")
    location_rns = map_locations_ids_to_resource_names(client, location_ids)
    language_rn = client.get_service("GoogleAdsService").language_constant_path(language_id)
    request = client.get_type("GenerateKeywordIdeasRequest")
    request.customer_id = str(customer_id)
    request.language = language_rn
    request.geo_target_constants.extend(location_rns)
    request.include_adult_keywords = False
    request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
    request.keyword_seed.keywords.extend(base_keywords)
    
    all_results = []
    try:
        response = keyword_plan_idea_service.generate_keyword_ideas(request=request)
        for idea in response.results:
            competition_enum = client.enums.KeywordPlanCompetitionLevelEnum
            competition_level = competition_enum.KeywordPlanCompetitionLevel.Name(
                idea.keyword_idea_metrics.competition)
            all_results.append({
                "Keyword": idea.text,
                "Avg Monthly Searches": idea.keyword_idea_metrics.avg_monthly_searches,
                "Competition": competition_level,
            })
    except GoogleAdsException as ex:
        st.error(f"Error with request: {ex}")
    return pd.DataFrame(all_results)

def scrape_google_search_results(keyword, hl, gl, num_results=10):
    API_KEY = st.secrets["serp_api"]
    search = GoogleSearch({
        "q": keyword,
        "num": num_results,
        "hl": hl,
        "gl": gl,
        "api_key": API_KEY
    })
    results = search.get_dict()
    search_results = [{"Title": r.get("title", "N/A"), "Description": r.get("snippet", "N/A")} for r in results.get("organic_results", [])[:num_results]]
    return pd.DataFrame(search_results)

def generate_ads(top_keywords, brand, serp_df_list, no_of_headlines, no_of_descriptions, hl, gl):
    ai_client = AzureChatOpenAI(api_key=st.secrets["openai_api"], api_version="2023-12-01-preview", azure_endpoint=st.secrets["openai_endpoint"], azure_deployment="gpt-data")
    guideline1 = f"1. Write compelling, genuine ad copy based on {', '.join(top_keywords)}."
    guideline2 = f"2. Reflect our brand {brand} in the messaging."
    guardrail = "Headlines: max 30 chars, Descriptions: max 90 chars."
    prompt = f"Generate {no_of_headlines} headlines and {no_of_descriptions} descriptions in {hl} for {gl} incorporating {serp_df_list}. Guidelines: {guideline1} {guideline2}. {guardrail}."
    response = ai_client.invoke(prompt)
    return response.content if response else "Error generating ads."

def main():
    st.set_page_config(page_title="Ad Copies Generator", layout="wide")

    # Title with LinkedIn button
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("Google Ads Keyword & Ad Generator")
    with col2:
        st.markdown("""
            <a href="https://www.linkedin.com/in/abhishek-kumawat-iitd/" target="_blank">
                <button style="background-color:#0077B5; color:white; border:none; padding:8px 16px; border-radius:5px; font-size:16px; cursor:pointer;">
                    Connect on LinkedIn
                </button>
            </a>
        """, unsafe_allow_html=True)

    col1, col2 = st.columns([1, 2])

    language_country_mapping = {
        "Dutch": {"hl": "nl", "language_code": 1010},
        "French": {"hl": "fr", "language_code": 1002},
        "Italian": {"hl": "it", "language_code": 1004},
        "Spanish": {"hl": "es", "language_code": 1003},
        "German": {"hl": "de", "language_code": 1001},
        "Danish": {"hl": "da", "language_code": 1009},
        "Norwegian": {"hl": "no", "language_code": 1013},
        "Swedish": {"hl": "sv", "language_code": 1015},
        "English": {"hl": "en", "language_code": 1000}
    }

    country_mapping = {
        "Belgium": {"gl": "BE", "location_code": 2056},
        "Netherlands": {"gl": "NL", "location_code": 2528},
        "France": {"gl": "FR", "location_code": 2250},
        "Italy": {"gl": "IT", "location_code": 2380},
        "Spain": {"gl": "ES", "location_code": 2724},
        "Germany": {"gl": "DE", "location_code": 2276},
        "Denmark": {"gl": "DK", "location_code": 2208},
        "Norway": {"gl": "NO", "location_code": 2578},
        "Sweden": {"gl": "SE", "location_code": 2752},
        "India": {"gl": "IN", "location_code": 2356}
    }

    with col1:
        st.header("Input Parameters")
        base_keywords = st.text_area("Enter base keywords (comma-separated)", "vakantiehuis").split(",")
        language = st.selectbox("Select Language", list(language_country_mapping.keys()))
        country = st.selectbox("Select Country", list(country_mapping.keys()))
        brand = st.selectbox("Select Brand", ["Belvilla", "DanCenter", "Danland", "OYO", "CheckMyGuest"])

        language_code = language_country_mapping[language]["language_code"]
        hl = language_country_mapping[language]["hl"]
        country_code = country_mapping[country]["location_code"]
        gl = country_mapping[country]["gl"]

        no_of_headlines = st.number_input("Number of Headlines", 5, 25, 20)
        no_of_descriptions = st.number_input("Number of Descriptions", 2, 10, 8)
        generate_button = st.button("Generate Keywords & Ad Copies")

    with col2:
        if generate_button:
            with st.spinner("Generating results, please wait..."):
                try:
                    st.header("Results")
                    credentials = {
                        "developer_token": st.secrets["developer_token"],
                        "client_id": st.secrets["client_id"],
                        "client_secret": st.secrets["client_secret"],
                        "refresh_token": st.secrets["refresh_token"],
                        "use_proto_plus": False,
                        "login_customer_id": st.secrets["login_customer_id"]
                    }

                    client = GoogleAdsClient.load_from_dict(credentials)
                    df = get_keyword_ideas_with_themes(client, "7186856567", [country_code], language_code, base_keywords)
                    top_keywords_df = df.sort_values(by="Avg Monthly Searches", ascending=False).head(10)
                    st.subheader("Top Keywords")
                    st.dataframe(top_keywords_df)

                    top_keywords = top_keywords_df["Keyword"].tolist()
                    
                    serp_df = scrape_google_search_results(",".join(base_keywords), hl, gl)
                    st.subheader("Google Search Results")
                    st.dataframe(serp_df)

                    generated_ads = generate_ads(top_keywords, brand, serp_df.to_dict(), no_of_headlines, no_of_descriptions, hl, gl)
                    st.subheader("Generated Ads")
                    st.text_area("", generated_ads, height=300)
                except Exception as e:
                    st.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
