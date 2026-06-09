# DESIGN.md

### User Customization
When deciding how to extend the usage of the menu scanner beyond understanding the ingredients and items, I drew upon my personal experience to allow for users to input their dietary restrictions. As someone with life-threatening allergies and dietary preferences, I find it difficult to identify foods I can safely eat when eating in more upscale restaurants. Being presented with a menu reading antipasta or l’entree induces a sense of stress only a select few others would understand. (The rest of the menu is likely to also include niche words and ingredients I’ll need to verify before eating.) This application makes reading the menu easier. 
Because of my history with this subject, this feels like a human decision. An AI was not the one to create this fear in me, nor was it what sparked me to find a solution for it.

### Eval
Creating a dataset that evaluates the LLM for identifying menus is difficult because neither menus nor their extracted texts are accessible as datasets online. Instead, I chose to manually create the golden dataset by scraping the internet for relevant images. There were two main objectives I needed to test in the AI from the evaluation set: that it could identify menus and that it could identify items from the menu correctly. Thus, my golden dataset is a mix of menus and non-menus. The subset of the dataset of menus also has its first item labelled. This hits both of my initial objectives while keeping the dataset manageable for a human. 
This feels like a human decision as the AI was the user, not the problem or solution, for my decision. 

### Stylistic Choices
From my history with design, I paid special attention to where elements of my commands resulted in the final UI. In one instance, I made the unique decision for two buttons to scan a new menu: one at the top of the document and one at the bottom. I made this decision distinctly in disagreement with the LLM to enforce having an accessible UI for users. This is because when the menu list gets long enough, or some are opened to display all of their items, it may be annoying for users to have to scroll all the way to one side of the page for the new menu button. Instead, offering this button on either side is most usable.
This felt like an organic decision because I was resisting the natural tendency of the agent. 