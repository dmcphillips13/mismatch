### Task 1: Articulate the problem and the user of your application
- Write a succinct 1-sentence description of the problem
- Write 1-2 paragraphs on why this is a problem for your specific user
- Create a list of questions or input-output pairs that you can use to evaluate your application

1. NHL bettors on Kalshi have no efficient way to determine whether a game's odds are mispriced compared to those on sportsbooks, forcing them to manually compare odds across multiple sources before every trade.

2. The target user is a person betting on NHL games on Kalshi. Kalshi is a prediction market, not a traditional sportsbook, so its prices are set by crowd consensus rather than oddsmakers. This creates a real opportunity: when Kalshi offers better odds than those of sportsbooks, there is a quantifiable "edge". The problem is that finding these edges manually is tedious and error-prone - for example, the bettor has to pull odds from multiple sportsbooks, do the math to get fair probabilities from the sportsbooks ("de-vig"), compare those to the current Kalshi odds, and then factor in other information like recent results, head-to-head history, and injuries before placing a trade.

   This workflow can be automated. The user can identify +EV opportunities (the odds being offered on Kalshi are better than those on the sportsbooks) and execute on them quickly, ideally before the market corrects. Without a tool that aggregates and compares this data in real time, the bettor either spends too long on manual research or misses edges entirely. Mismatch solves this by doing the odds math, the retrieval of historical context, and the recommendation in a chat interface.

3. Evaluation questions:
   - "How have the Bruins and Maple Leafs done head-to-head in 2024-25?"
   - "Who has the edge when the Rangers play the Penguins at home?"
   - "Are the Jets on a hot streak, and how have they done against the Wild recently?"
   - "How did the Capitals vs Penguins matchup in 2023-24 compare to 2024-25?"
   - "How have the Golden Knights and Kings matched up across the last few seasons?"


### Task 2: Articulate your proposed solution
1. Write 1-2 paragraphs on your proposed solution.  How will it look and feel to the user? Describe the tools you plan to use to build it.
2.  Create an infrastructure diagram of your stack showing how everything fits together.  Write one sentence on why you made each tooling choice.
    1. LLM(s)
    2. Agent orchestration framework
    3. Tool(s)
    4. Embedding model
    5. Vector Database
    6. Monitoring tool
    7. Evaluation framework
    8. User interface
    9. Deployment tool
    10. Any other components you need
3. What are the RAG and agent components of your project, exactly?

1. <!-- TODO -->

2. <!-- TODO -->

3. <!-- TODO -->


### Task 3: Collect your own data (RAG) and choose at least one external API to use (Agent)
1. Describe the default chunking strategy that you will use for your data.  Why did you make this decision?
2. Describe your data source and the external API you plan to use, as well as what role they will play in your solution. Discuss how they interact during usage.

1. <!-- TODO -->

2. <!-- TODO -->


### Task 4: Build an end-to-end Agentic RAG application using a production-grade stack and your choice of commercial off-the-shelf model(s)
1. Build an end-to-end prototype and deploy it to a *local* endpoint
2. (Optional) Use locally-hosted OSS models instead of LLMs through the OpenAI API
3. (Optional) Deploy your prototype to public endpoint using a tool like [Vercel](http://vercel.com/), [Render](https://render.com/), or [FastAPI Cloud](https://fastapicloud.com/)

<!-- DELETE ? -->


### Task 5: Prepare a test data set (either by generating synthetic data or by assembling an existing dataset) to baseline an initial evaluation with RAGAS
1. Assess your pipeline using the RAGAS framework, including the following key metrics: faithfulness, context precision, and context recall. Include any other metrics you feel are worthwhile to assess.   Provide a table of your output results.
2. What conclusions can you draw about the performance and effectiveness of your pipeline with this information?

1. <!-- TODO -->

2. <!-- TODO -->


### Task 6: Install an advanced retriever of your choosing in our Agentic RAG application
1. Choose an advanced retrieval technique that you believe will improve your application’s ability to retrieve the most appropriate context.  Write 1-2 sentences on why you believe it will be useful for your use case.
2. Implement the advanced retrieval technique on your application.
3. How does the performance compare to your original RAG application?  Test the fine-tuned embedding model using the RAGAS frameworks to quantify any improvements.  Provide results in a table.

1. <!-- TODO -->

2. <!-- TODO -->

3. <!-- TODO -->


### Task 7: Next Steps
1. Do you plan to keep your RAG implementation via Dense Vector Retrieval for Demo Day? Why or why not?

1. <!-- TODO -->
