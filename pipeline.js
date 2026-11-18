import fs from 'fs/promises';
import { ADK_AGENTS } from './agents.js';
import { fetchLiveFeed, executeAgentWithReflection } from './ingest.js';

async function runAutonomousPipeline() {
    console.log(`\n==========================================`);
    console.log(`   AYO'S DEN: AUTONOMOUS RUNTIME CYCLE`);
    console.log(`==========================================`);

    // Step 1: Trigger Live Ingestion
    const feed = await fetchLiveFeed();
    console.log(`[Ingestion] Captured live target: "${feed.rawText}"\n`);

    // Step 2: Execute Agent 1 with Self-Correction Wrapper
    const sentiment = await executeAgentWithReflection(
        "Agent 1 (Sentiment Indexer)",
        ADK_AGENTS.sentimentIndexer.run,
        feed.rawText
    );

    // Step 3: Execute Agent 4 (Competitor Auditor) with Reflection
    const velocityCheck = await executeAgentWithReflection(
        "Agent 4 (Competitor Auditor)",
        ADK_AGENTS.competitorAuditor.run
    );

    // Step 4: Execute Agent 2 (Distribution Strategist) with Reflection
    const metadata = await executeAgentWithReflection(
        "Agent 2 (Distribution Strategist)",
        ADK_AGENTS.distributionStrategist.run,
        sentiment,
        "breaking_news"
    );

    // Step 5: Execute Agent 3 (Script Architect) with Reflection
    const script = await executeAgentWithReflection(
        "Agent 3 (Script Architect)",
        ADK_AGENTS.scriptArchitect.run,
        metadata
    );

    const payload = {
        id: Date.now(),
        timestamp: new Date().toISOString(),
        ingestionSource: feed.source,
        rawInput: feed.rawText,
        agentResults: { sentiment, velocityCheck, metadata, script },
        status: "Autonomous-Staged"
    };

    // Step 6: Commit Payload to Persistent Queue State
    const queueFile = 'queue.json';
    let queue = [];
    try {
        const data = await fs.readFile(queueFile, 'utf-8');
        queue = JSON.parse(data);
    } catch (err) { }

    queue.push(payload);
    await fs.writeFile(queueFile, JSON.stringify(queue, null, 2));

    console.log(`==========================================`);
    console.log(`[Queue State] Payload successfully committed to ${queueFile}`);
    console.log(`==========================================\n`);
}

// Run the autonomous pipeline loop
runAutonomousPipeline();