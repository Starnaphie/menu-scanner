## Review by Vats Narsaria, A17301126
## Review of Stephanie Xu

### 1. Project summary/implementation

#### a. Summary
The project is a menu scanning application that takes an image of a restaurant menu as input, along with optional user-provided dietary restrictions. The system extracts structured information such as menu items, ingredients, and potential allergens, and then annotates items based on dietary filters.

#### b. GUI/backend interface
The application uses a backend API with multiple endpoints to process user input. The GUI sends a `POST` request to the `/scan` endpoint with the uploaded menu image, which performs initial parsing and extraction. A second `POST` request is made to the `/refine-item` endpoint, which refines the extracted data and includes dietary restriction logic. The backend is a two-stage pipeline where extraction and refinement are handled separately.

#### c. User data in the prompt
User data influences the prompt in multiple stages of the pipeline. In `extractor.py`, the uploaded menu image is processed as part of the first-stage prompt for extraction. In the second stage, user-provided dietary restrictions are included in the prompt to refine the extracted items and assign dietary or allergen tags. The user input is not fully integrated into a single prompt but instead injected during refinement.

#### d. One confusing thing
One confusing part was the inconsistent dietary labeling. For example, items with cheese were not marked as dairy, while a “beef” flag showed up even when it wasn’t part of the user’s restrictions. It’s not clear whether this issue comes from the extraction stage, the refinement step, or the prompt logic.

### 2. Suggestions

#### a. Optimization/improvement of existing features
The two-stage pipeline (extraction + refinement) likely adds extra latency due to multiple API calls. One improvement would be to revisit a single-stage approach with a better prompt that handles both extraction and dietary filtering together. Even though this was less accurate before, using more structured prompts or examples could improve accuracy while reducing latency and overall complexity.

#### b. Extension/feature request
A useful extension would be letting users save favorite restaurants or menu items and get recommendations later. This could be done by storing past results and user preferences, then suggesting similar items that match their dietary restrictions. This would make the app more useful beyond just one-time scans.

# Feeback Response
I addressed all of the above concerns. My priority was fixing the dietary labelling tags as they were core to the appeal of my project. I identified the issue as vagueness in my second prompt, ultimately a result of vagueness in the first prompt. I embarked on a series of experiments with the prompts of either LLM stages to ensure the dietary flags were recorded accurately and consistently. This worked properly by the time I reached [this commit](https://github.com/ucsd-cse-genai-programming-sp26/02-doc-scanner-steef/commit/c016932fc1e56867355a0c46f731d678ca37310e).

The latency issues were difficult to fix. Combining both stages of the pipeline resulted in messy dietary flags that the LLM was not confident on. Instead, I made the latency more bearable: I separated not only the backend into 2 stages, but the frontend experience as well. This brought the user into the equation of first verifying the item name and description parsing, then the dietary flags generated. Not only does this make the latency seem better, it also makes the stage 2 input more accurate, by prompting the user. This is present by [this commit](https://github.com/ucsd-cse-genai-programming-sp26/02-doc-scanner-steef/commit/c016932fc1e56867355a0c46f731d678ca37310e).

I implemented a favorites system to allow users to star and record their previous menus. This lets them find and rereference previous menus for the items they had tried before, while preserving the dietary flags. The foundation for a future recommendations feature is in place, but I ran into time constraints to fully flesh this out. This completed star system is present in [this commit](https://github.com/ucsd-cse-genai-programming-sp26/02-doc-scanner-steef/commit/5e2f40860501d55893d7f4377d5e65b6cf41800d).

## Review by Oleg Bychenkov, A17513882
## Review of Stephanie Xu

### 1. Project summary/implementation

#### a. Summary
_Summarize the project in a few sentences: what kind of documents does it take, what interface does it present, what does it extract?_

Scan an image of a menu, can include your dietary restrictions. Interface is a list menu items with their list of ingredients, sorted by tags of dietary restrictions. Also describes any "obscure" ingredients the user might not be familiar with.

#### b. GUI/backend interface
_What is the programmatic interface between the GUI and the backend that sends the user document to the backend? Be specific: identify the URL route, the parameters, HTTP method, API call, etc._

URL: 0.0.0.0:8000
HTTP methods: GET, POST

API Calls:
INFO: Started reloader process [4107] using WatchFiles
INFO: Started server process [4112]
INFO: Waiting for application startup.
INFO: Application startup complete.
INFO: 127.0.0.1:55697 - "GET / HTTP/1.1" 200 OK
INFO: 127.0.0.1:55698 - "GET / HTTP/1.1" 200 OK
INFO: 127.0.0.1:55705 - "POST /scan HTTP/1.1" 200 OK
INFO: 127.0.0.1:55764 - "OPTIONS /refine-item HTTP/1.1" 200 OK
INFO: 127.0.0.1:55764 - "POST /refine-item HTTP/1.1" 200 OK

#### c. User data in the prompt
_Identify the place in the code/prompt where user data had an effect (e.g. templated into/included in the prompt, used to inform data that is part of the prompt)._

User inputs a photo of a menu. Input gets extracted in the first stage into a json, then refined in stage 2, including handling dietary restrictions. 

#### d. One confusing thing
_Identify one thing you find confusing in the implementation, and describe why it's confusing and what you tried reading to understand it._

Unclear how tags work sometimes, tags that aren't originally filtered for can appear, especially if the user makes edits. It's not obvious why those sometimes pop up despite filtering for only the tags the user specified. 

### 2. Suggestions

#### a. Optimization/improvement of existing features
_Suggest one thing you would try to substantially improve the cost, latency, or accuracy of the application without compromising on other aspects. Give a substantive argument for why it's a good idea, grounded in details of the implementation (not just "use a smaller model")._

One idea to improve latency slightly could be to have everything be in one prompt instead of 2 stages, since it ends up creating a JSON, and then the 2nd prompt has to process that JSON, wheras one prompt could just go directly from the image to the final result. Though it was mentioned that this was done for better tagging accuracy, so it would be a tradeoff.

#### b. Extension/feature request
_Which of the official required extensions would you suggest for this project? How would you go about it? (The reviewee isn't forced to do this one; this is for you to think a little bit about what it would look like on an unfamiliar codebase)_

Having a login and user system to save menu scans, and potentially add a system for users to save which restaurants or menu items are their favorites. Just having a username/email and password database is probably the easiest way to go about it, and that database can also be used to store a list of favorite items/restaurants per user.

# Feedback Response
As addressed in the previous feedback, I fixed my tags through prompt editing, present in [this commit](https://github.com/ucsd-cse-genai-programming-sp26/02-doc-scanner-steef/commit/c016932fc1e56867355a0c46f731d678ca37310e). 

Again, I chose a third option in the latency and accuracy tradeoff, keeping both while fixing the user experience around it, evident in [this commit](https://github.com/ucsd-cse-genai-programming-sp26/02-doc-scanner-steef/commit/c016932fc1e56867355a0c46f731d678ca37310e). 

I added in a login and user system to allow users to save menus, stars, and dietary flags to their specific account! This makes the application much more usable, even on the same device. This went hand-in-hand with the star system referenced earlier as stars and dietary flags are saved specifically to a user's profile. This is present in [this commit](https://github.com/ucsd-cse-genai-programming-sp26/02-doc-scanner-steef/commit/337b9d40297605b37cdba616c80be10e8f848f0e).