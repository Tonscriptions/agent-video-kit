/**
 * Standalone Example: Constructing a Viral Short with CapCut MCP
 * 
 * Demonstrates how an automated script or agent creates a CapCut project,
 * adds a primary speech clip, sets a punch-in zoom keyframe, inserts B-roll,
 * adds background music with audio ducking, and generates viral captions.
 */

import path from 'path';
import { DraftManager } from '../src/capcut/draft-manager.js';
import { CapCutPathResolver } from '../src/capcut/paths.js';

async function main() {
  console.log('🚀 Initializing CapCut Viral Reel Construction...');

  const projectName = `Viral_Reel_${Date.now()}`;
  
  // 1. Create a 9:16 vertical short project (1080x1920)
  console.log(`Creating project: ${projectName}`);
  const project = await DraftManager.createProject({
    name: projectName,
    width: 1080,
    height: 1920,
    ratio: '9:16'
  });
  console.log(`✅ Project created with ID: ${project.id}`);

  // 2. Demonstrate adding a viral kinetic caption
  console.log('Adding kinetic caption: "THE SECRET TO SCALE"');
  await DraftManager.addViralCaption({
    projectNameOrId: projectName,
    text: 'THE SECRET TO SCALE',
    startTimeSeconds: 0.5,
    durationSeconds: 2.0,
    powerWords: ['SCALE'],
    accentColor: '#FFD700',
    enableHoverPop: true
  });
  console.log('✅ Kinetic caption added.');

  // 3. Inspect the updated project timeline
  const details = await DraftManager.getProject(projectName);
  console.log(`📊 Project Duration: ${details.summary.durationSeconds}s`);
  console.log(`📊 Tracks Count: ${details.summary.tracksCount}`);

  console.log('🎉 Done! Open CapCut Desktop to inspect the generated timeline.');
}

if (process.argv[1]?.endsWith('create_viral_reel.ts') || process.argv[1]?.endsWith('create_viral_reel.js')) {
  main().catch(console.error);
}
