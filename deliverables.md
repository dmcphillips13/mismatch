## Loom Video: [TODO]

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
- Write 1-2 paragraphs on your proposed solution. How will it look and feel to the user? Describe the tools you plan to use to build it.
- Create an infrastructure diagram of your stack showing how everything fits together.  Write one sentence on why you made each tooling choice.
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
- What are the RAG and agent components of your project, exactly?

1. Mismatch is a chatbot where the user types a question and gets back a structured response with odds tables, bet or pass recommendations, and supporting rationale. The frontend is a Next.js app that sends messages to a Python FastAPI backend, where a LangGraph agent pipeline handles the query. The pipeline first classifies the user's intent (slate discovery, matchup check, explanation, or general), then retrieves relevant historical context from Qdrant, fetches live odds from the Odds API and Kalshi, computes the edge between the two, optionally searches for injury/goalie news via Tavily, and uses all of this context to generate a response. For the response, the LLM only generates rationale text, not the odds tables or recommendations, which prevents hallucinated numbers.

   The user experience is conversational. You can ask "What games are +EV tonight?" and get a full slate of games with edges, or ask about a specific team and get a focused matchup breakdown. The system always cites its sources (retrieved docs, Odds API, Tavily links) and adds a disclaimer noting that this is not financial advice. The goal is for the user to get in a few seconds what would otherwise take 10-15 minutes of manual research across multiple sites.

2. Infrastructure diagram:

   ```
   ┌─────────────────┐     ┌─────────────────────────────────────────────┐
   │   Next.js UI    │────▶│           FastAPI Backend                   │
   │                 │◀────│                                             │
   └─────────────────┘     │  ┌─────────────────────────────────────┐    │
                           │  │         LangGraph Pipeline          │    │
                           │  │                                     │    │
                           │  │  interpret_intent (OpenAI gpt-4o-mini)   │
                           │  │        │                            │    │
                           │  │        ▼                            │    │
                           │  │  retrieve (Qdrant)                  │    │
                           │  │        │                            │    │
                           │  │        ▼                            │    │
                           │  │  fetch_odds_and_kalshi              │    │
                           │  │  (Odds API + Kalshi API)            │    │
                           │  │        │                            │    │
                           │  │        ▼ (conditional)              │    │
                           │  │  tavily_search (if BET or explain)  │    │
                           │  │        │                            │    │
                           │  │        ▼                            │    │
                           │  │  generate_response (OpenAI)         │    │
                           │  └─────────────────────────────────────┘    │
                           │                                             │
                           │  LangSmith (tracing + eval datasets)        │
                           └─────────────────────────────────────────────┘
                                         │           │
                              ┌──────────┘           └──────────┐
                              ▼                                  ▼
                     ┌────────────────┐               ┌──────────────────┐
                     │  Qdrant Cloud  │               │  External APIs   │
                     │  (mismatch_docs│               │  - Odds API      │
                     │   collection)  │               │  - Kalshi        │
                     └────────────────┘               │  - Tavily        │
                                                      │  - NHL API       │
                                                      └──────────────────┘
   ```

   Tooling choices:
   1. **LLM:** This uses gpt-4o-mini because it is fast, cheap, and capable enough for intent classification and rationale generation where the heavy lifting is done deterministically.
   2. **Agent orchestration:** This uses LangGraph to give us control over the node pipeline and conditional edges, which is important because the Tavily search is conditional based on whether there's a bet recommendation or an explanation request.
   3. **Tools:** We use the Odds API for sportsbook consensus odds, the Kalshi API for prediction market prices, Tavily for web search for injuries/news, and the NHL API for live scores and schedule data.
   4. **Embedding model:** This uses text-embedding-3-small for a good balance of cost and quality for embedding pre-computed summary documents.
   5. **Vector database:** This uses Qdrant Cloud with cosine distance because this supports metadata filtering by team, season, and doc type, which is critical for retrieving the right head to head or form summary for a given matchup.
   6. **Monitoring:** This uses LangSmith to provide tracing for every agent run and to host the evaluation datasets, making it easy to compare retrieval experiments.
   7. **Evaluation:** This uses RAGAS to give us standardized metrics (faithfulness, context recall, answer relevancy) to measure retrieval quality and track improvements.
   8. **User interface:** This uses Next.js with React to create a thin chat UI frontend that sends requests to the Python backend, keeping all agent logic in Python. This also makes deployment easier with Vercel.
   9. **Deployment:** This will use public deployment via Vercel and a cloud host for the backend. We chose Next.js for ease of Vercel deployment.
   10. **NHL API:** The public NHL Stats API provides live scores, game states, and team schedules, which the pipeline uses to show real-time game status. **Edge computation:** A deterministic math layer de-vigs the sportsbook odds into fair probabilities and compares them to Kalshi's odds to produce an edge for each side of a game.

3. The RAG component is the Qdrant retrieval layer. It stores 2,251 pre-computed summary documents (team season summaries, head-to-head season summaries, and recent H2H rolling summaries) generated from three seasons of NHL CSV data. When a user asks a question, the pipeline embeds the query, searches Qdrant with optional metadata filters (team name, season, doc type), and passes the retrieved context to the LLM for rationale generation.

   The agent component is the LangGraph pipeline that orchestrates the full workflow. It classifies intent, calls the retrieval layer, fetches live data from four external APIs (Odds API, Kalshi, NHL API, Tavily), computes the mathematical edge between sportsbook fair probability and Kalshi's implied probability, and assembles the response. The conditional Tavily node is the clearest example of agent behavior — the system decides whether to search for news based on whether it found a +EV edge or the user asked for an explanation.


### Task 3: Collect your own data (RAG) and choose at least one external API to use (Agent)
1. Describe the default chunking strategy that you will use for your data.  Why did you make this decision?
2. Describe your data source and the external API you plan to use, as well as what role they will play in your solution. Discuss how they interact during usage.

1. The pipeline uses `RecursiveCharacterTextSplitter` with `chunk_size=500` and `chunk_overlap=50`, but the true chunking strategy is within the step before that when the documents are built. This reads three seasons of NHL game data from CSV files and aggregates the raw game records into 2,251 natural language summaries across five document types (team season summaries, a team's last 10 games, a team's last 20 games, head-to-head season summaries, and head-to-head matchups). Each summary is a self-contained paragraph with stats like win rate, goals per game, home/away splits, rest days, and back-to-back rate, and each one comes in under 500 characters by design. This results in the splitter passing these documents through unchanged, which is intentional. The raw data is structured (CSV rows of game results), not unstructured text, meaning that the real "chunking" decision is how to aggregate those rows into retrieval docs. Pre-computing small, structured summaries means every document in Qdrant is a complete, coherent doc (i.e no partial stat lines). The `RecursiveCharacterTextSplitter` acts as a guardrail in the pipeline in case future document types (i.e. Wikipedia articles about a team's season) exceed the threshold, but for the current data it's a no-op by design.

2. The data is three full seasons of regular season NHL results in CSV format from "Shane's Computer Solution Repository", each containing scores, dates, home/away, etc. These are processed into the summary documents described above and stored in Qdrant Cloud, where they serve as the RAG context for matchup history and team form questions.

   The external APIs serve different roles in the agent pipeline. The Odds API provides current sportsbook odds for upcoming games, which the pipeline de-vigs into fair probabilities. The Kalshi API provides the current prediction market prices for the same games. The compute_edges node compares these two to produce a numerical edge. Tavily is used as a web search tool when the system finds a +EV edge or the user asks for an explanation, pulling recent injury reports and news. The NHL API provides live game scores, states, and team schedules to show real-time status.

   For a user query, Qdrant first retrieves the relevant historical context (i.e. how two teams have matched up this season), the Odds API and Kalshi provide the live odds for the edge calculation, and Tavily optionally adds current news to round out the rationale. The LLM then uses all of this context to generate the rationale bulletpoints, while the odds tables and recommendations are formatted deterministically from the edge data.

### Task 4: Build an end-to-end Agentic RAG application using a production-grade stack and your choice of commercial off-the-shelf model(s)
- Vercel: https://mismatch-kohl.vercel.app
- Backend: https://mismatch-agent.onrender.com

### Task 5: Prepare a test data set (either by generating synthetic data or by assembling an existing dataset) to baseline an initial evaluation with RAGAS
1. Assess your pipeline using the RAGAS framework, including the following key metrics: faithfulness, context precision, and context recall. Include any other metrics you feel are worthwhile to assess.   Provide a table of your output results.
2. What conclusions can you draw about the performance and effectiveness of your pipeline with this information?

1. The test dataset contains 51 synthetic queries generated by RAGAS `TestsetGenerator` using a mix of single-hop specific (50%), multi-hop abstract (25%), and multi-hop specific (25%) strategies across a sample of 100 documents (took too long to use all of the documents). The baseline uses dense cosine retrieval from Qdrant (top 6 documents) with gpt-4o-mini for generation.

   | Metric                 | Score    |
   |------------------------|----------|
   | Faithfulness           | 0.8815   |
   | Context Precision      | 0.5859   |
   | Context Recall         | 0.7271   |
   | Context Entity Recall  | 0.3333   |
   | Answer Relevancy       | 0.6032   |
   | Factual Correctness    | 0.4092   |
   | Avg Latency            | 2,571ms  |
   | Avg Cost / Query       | $0.0002  |

2. Faithfulness is the strongest metric (0.88), which means the LLM is mostly grounding its answers in the retrieved context rather than hallucinating. This makes sense given that the pipeline uses math for the odds tables and only asks the LLM to generate rationale text from the provided docs.

   Context precision (0.59) measures whether the retrieved documents that appear early in the results are actually relevant to generating the correct answer. At 0.59, this tells us that roughly 40% of the top-ranked retrieved docs aren't contributing meaningfully to the answer, suggesting room for retrieval reranking to push more relevant docs to the top.

   Context recall (0.73) shows that nearly 30% of the ground truth facts aren't making it into the retrieved context, which is decent but shows room for improvement. This is likely because the retrieval limit of 6 docs sometimes misses relevant summaries when a question spans multiple teams or seasons.

   Answer relevancy (0.60) suggests some responses drift from the original question (likely on multi-hop queries where the pipeline retrieves context for one team but not the other). This is the clearest signal for where advanced retrieval could help.

   Factual correctness (0.41) reflects the gap between the synthetic reference answers (generated from source docs) and the pipeline's actual output, which reformulates the stats into a different structure. Entity recall (0.33) is a bit low because the summaries are stat-heavy (i.e. win rates, averages) rather than entity-rich (i.e. player names) and RAGAS's entity matching doesn't capture the relevant information well. These two metrics are worth watching but could be due to how the test set was generated rather than actual issues.


### Task 6: Install an advanced retriever of your choosing in our Agentic RAG application
1. Choose an advanced retrieval technique that you believe will improve your application’s ability to retrieve the most appropriate context.  Write 1-2 sentences on why you believe it will be useful for your use case.
2. Implement the advanced retrieval technique on your application.
3. How does the performance compare to your original RAG application?  Test the fine-tuned embedding model using the RAGAS frameworks to quantify any improvements.  Provide results in a table.

1. I chose Cohere reranking (rerank-english-v3.5) for my advanced retrieval technique. The baseline retrieves 6 docs by cosine similarity, which works well for single-team queries but struggles on multi-hop questions where the relevant docs aren't necessarily the closest embeddings. Reranking retrieves a wider initial set (10 docs) and then rescores them by semantic relevance to the query, prioritizing the most useful docs rather than just the nearest vectors.

2. The implementation uses LangChain's `ContextualCompressionRetriever` wrapping the existing Qdrant retriever. It fetches 10 candidates via dense cosine search, then Cohere reranks them and returns the top 5. This is integrated into the eval pipeline as a separate `build_reranked_rag_chain()` that shares the same generation step as baseline.

3. Results across 51 examples:

   | Metric                | Baseline | Reranked | Delta   |
   |-----------------------|----------|----------|---------|
   | Faithfulness          | 0.8815   | 0.8694   | -0.0121 |
   | Context Precision     | 0.5859   | 0.6693   | +0.0833 |
   | Context Recall        | 0.7271   | 0.7578   | +0.0307 |
   | Context Entity Recall | 0.3333   | 0.3558   | +0.0225 |
   | Answer Relevancy      | 0.6032   | 0.6528   | +0.0496 |
   | Factual Correctness   | 0.4092   | 0.4278   | +0.0186 |
   | Avg Latency           | 2,571ms  | 6,335ms  | +3,764ms |
   | Avg Cost / Query      | $0.0002  | $0.0001  | ~$0     |

   Reranking improved five of the six metrics. Context precision saw the largest gain (+0.0833), due to Cohere's reranking pushing more relevant documents to the top of the results and giving the LLM better context to work with. Answer relevancy (+0.0496), context recall (+0.0307), context entity recall (+0.0225), and factual correctness (+0.0186) all improved as well.

   Faithfulness dipped slightly (-0.0121) but remained high at 0.87. Latency (+3,764ms) took a hit due to the extra Cohere API call. Cost per query stayed roughly the same due to rerank passing 5 focused docs to the LLM instead of 6, saving on generation tokens and roughly offsetting it.


### Task 7: Next Steps
1. Do you plan to keep your RAG implementation via Dense Vector Retrieval for Demo Day? Why or why not?

Full disclosure, I'm planning to do a different project for demo day - this project was created specifically for the certification challenge due to RAG being more relevant for it. If I were to continue with Mismatch I would keep the Cohere reranking over the baseline dense retrieval, as the context precision and context recall gains are worth the latency tradeoff in this context (and the faithfulness remains high). I'd rather have a user wait an extra few seconds for a well-grounded answer than get a faster response that misses relevant context or hallucinates stats. Latency matters less here because the user is making a betting decision, not having a real-time conversation.
