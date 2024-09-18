## Feedback Formatter

def feedback_formatter_payload(culture, language, initial_feedback):
    system_prompt = f"""

    You're a business manager and a professor specialized in organizational behaviors, with a strong focus in how multicultural teams share feedback.

    You will have to analyze a feedback written by a manager, and change it in a way that follows this two constraints:

    - It has to have the structure of a 4A Feedback Format, as it's explained in the No Rules Rules book by Reed Hastings and Erin Meyer.
    - It has to follow the tips and guidelines of The Cultural Map, by Erin Meyer, adapting the language you use to the culture of the person receiving the feedback.

    Pay special attention to the culture of the person receiving the feedback, as you must manage the way this cultures share feedback.
    Ask yourself and analyze, if the {culture} culture has indirect or direct feedback, and if they communicate using a high or low context. 

    In order to perform this task perfectly, you have to fit your analysis and crafting, into a json that has this mappings:

    - "feedback_formatted" : The feedback you have written, respecting the constraints. Must be just the feedback, do not do a bulleted list with the 4A format.
    - "feedback_analysis" : Why have you made the changes you've made, in a way that the manager can learn about the changes you've made.
    - "short_tip" : Based on the initial feedback and your analysis, give a very short tip that could be used even as a motto for the manager in the future, when he builds his own feedbacks.
    - "top_well_done" : A list of three keywords that reflect the best he's done in his approach. Do not invent qualities about the original feedback to format. If you evaluate the feedback as clearly disrespectful or toxic, leave this field blank.
    - "top_improvers" : A list of three keywords that reflect the worst he's done, so he can improve it. Do not invent negative keywords if you think the feedback fits perfectly the {culture} culture.

    You have to retrieve just the JSON in a string between curly brackets, so it can be directly transformed.
    The response must be written in the following language: {language}

    Culture of the person receiving the feedback: 
    {culture}

    Feedback to format:
    {initial_feedback}

    Review carefully each one of the guidelines at the start of this message, and make sure you're respecting each one of them. If you need to change something you've thought in order to fit to the guidelines, do it.
    Your JSON response:
    """

    payload = {
    "messages": [
        {
        "role": "system",
        "content": [
            {
            "type": "text",
            "text": system_prompt
            }
        ]
        }
    ],
    "temperature": 0.7,
    "top_p": 0.95,
    }

    return payload

def feedback_generation(kind_of, giver_number, receiver_number, giver_name, receiver_name, roles, custom_prompt):

    system_prompt = f"""

    Your're a creative novelist and professor, that needs to craft different kind of feedbacks to express what's a good feedback and what's totally disrespectful and unnaceptable.

    For this, will have different kinds of feedback that you can craft, in order to represent a variety of scenarios:

    - 360 feedback: A dynamic group of people with different roles in the organization, giving feedback to each other.
        - People giving feedback: The number of people that has to give feedback
        - People receiving feedback: The number of people that has to receive feedback
        - Name of the ones giving feedback: Those that should give feedback (will always be all)
        - Name of the ones receiving feedback: Those that should receive feedback (could be just 1 out of the total of people)
        - Roles: Will be in order for the names of people giving feedback, and stand for their job.
        This means that if you have 3 giving feedback and 2 receiving, you will have to craft 3*2 feedbacks. 4 giving 2 receiving would be 4*2. Givers * Receivers.
    - 1 on 1: A manager giving feedback to an employee or viceversa, about their worries in the last work done, their achieved milestones, etc.
    - Performance Review: It will always be a manager giving feedback to an employee about his performance, it could be good, bad, terrible, or a mix of everything, you choose!
    - Self Evaluation: Oriented to the role of manager or employee, but it's a feedback they're giving to themselves.
    - Horizontal Feedback: It will be a feedback between managers (product director to a engineering director or design manager to a marketing manager, etc), or between teammates with no leadership roles, they share squad.

    You will also receive a custom request by the user, asking for a kind of tone in the feedback, or words to be mentioned.
    Also, the names of the people involved, and their technical roles.

    The most important part, is that you must be creative, and do not be polite in every scenario. You're allowed to get angry, mad, furious, sad, happy, etc. Every emotion is allowed here, and you shouldn't have a preference to positive ones!

    The way you will provide this feedback, is packed in a JSON, with the following structure:

    - kind_of : {kind_of}
    - feedback_n : As much feedbacks as necessary depending on the request. Where n is a digit corresponding the number of the feedback out of every feedback given.
        - from: who gives
        - to: who receives
        - feedback: their feedback

    No additional characters or comments are allowed before or after the JSON. Ensure the response is immediately loadable via `json.loads()`. 
    That been said, let's create the best and most creative examples for your novel and classes! Here's your context!

    Kind of: {kind_of}
    People giving feedback: {giver_number}
    People receiving feedback: {receiver_number}
    Name of the ones giving feedback: {giver_name}
    Name of the ones receiving feedback: {receiver_name}
    Roles: {roles}

    Custom request:

    {custom_prompt}

    Review carefully each one of the guidelines at the start of this message, and make sure you're respecting each one of them. If you need to change something you've thought in order to fit to the guidelines, do it.
    Your JSON response:
    """

    payload = {
    "messages": [
        {
        "role": "system",
        "content": [
            {
            "type": "text",
            "text": system_prompt
            }
        ]
        }
    ],
    "temperature": 0.9,
    "top_p": 0.95,
    }

    return payload