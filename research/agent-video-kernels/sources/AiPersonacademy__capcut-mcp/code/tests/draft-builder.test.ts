import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'fs/promises';
import path from 'path';
import os from 'os';
import { execFile } from 'child_process';
import { promisify } from 'util';
import { CapCutPathResolver } from '../src/capcut/paths.js';
import { DraftManager } from '../src/capcut/draft-manager.js';
import { SrtParser } from '../src/utils/srt-parser.js';
import { MediaProbe } from '../src/capcut/media.js';

const execFileAsync = promisify(execFile);

test('CapCut MCP Server - Comprehensive Suite', async (t) => {
  // Setup isolated temporary test directory
  const tempDir = path.join(os.tmpdir(), `capcut_mcp_test_${Date.now()}`);
  await fs.mkdir(tempDir, { recursive: true });
  CapCutPathResolver.setDraftsDirectory(tempDir);

  const testVideoPath = path.join(tempDir, 'sample_clip.mp4');
  const testAudioPath = path.join(tempDir, 'sample_audio.mp3');

  // Generate synthetic test media using ffmpeg
  try {
    await execFileAsync('ffmpeg', [
      '-y',
      '-f', 'lavfi', '-i', 'testsrc=duration=3:size=720x1280:rate=30',
      '-f', 'lavfi', '-i', 'sine=frequency=440:duration=3',
      '-c:v', 'libx264', '-c:a', 'aac', '-pix_fmt', 'yuv420p',
      testVideoPath
    ]);

    await execFileAsync('ffmpeg', [
      '-y',
      '-f', 'lavfi', '-i', 'sine=frequency=880:duration=4',
      '-c:a', 'libmp3lame',
      testAudioPath
    ]);
  } catch (err) {
    console.warn('ffmpeg test media generation skipped (if lavfi unavailable):', err);
  }

  await t.test('SrtParser parses standard SRT format accurately', () => {
    const srt = `
1
00:00:01,000 --> 00:00:03,500
Welcome to this video!

2
00:00:03,800 --> 00:00:06,200
Here is the second caption.
    `.trim();

    const cues = SrtParser.parse(srt);
    assert.equal(cues.length, 2);
    assert.equal(cues[0].startTimeSeconds, 1.0);
    assert.equal(cues[0].endTimeSeconds, 3.5);
    assert.equal(cues[0].text, 'Welcome to this video!');
    assert.equal(cues[1].startTimeSeconds, 3.8);
    assert.equal(cues[1].endTimeSeconds, 6.2);
    assert.equal(cues[1].text, 'Here is the second caption.');
  });

  await t.test('DraftManager creates a 9:16 project and registers in root meta', async () => {
    const project = await DraftManager.createProject({
      name: 'UnitTest_Project',
      ratio: '9:16'
    });

    assert.equal(project.name, 'UnitTest_Project');
    assert.equal(project.resolution, '1080x1920');
    assert.equal(project.ratio, '9:16');
    assert.equal(project.durationSeconds, 0);

    // Verify root_meta_info.json
    const rootMeta = await CapCutPathResolver.readRootMeta();
    assert.equal(rootMeta.all_draft_store.length, 1);
    assert.equal(rootMeta.all_draft_store[0].draft_name, 'UnitTest_Project');

    // Verify draft_content.json
    const details = await DraftManager.getProject('UnitTest_Project');
    assert.equal(details.draftContent.canvas_config.ratio, '9:16');
    assert.equal(details.draftContent.canvas_config.width, 1080);
    assert.equal(details.draftContent.canvas_config.height, 1920);
    assert.equal(details.draftContent.tracks.length, 1);
  });

  // Test real media probe and clip insertion if media was generated
  let createdVideoSegmentId = '';
  await t.test('MediaProbe and addVideoClip with synthetic video', async () => {
    const probe = await MediaProbe.probeFile(testVideoPath);
    assert.equal(probe.hasVideo, true);
    assert.equal(probe.width, 720);
    assert.equal(probe.height, 1280);

    const clipResult = await DraftManager.addVideoClip({
      projectNameOrId: 'UnitTest_Project',
      filePath: testVideoPath,
      startTimeSeconds: 'auto_append'
    });

    assert.ok(clipResult.segmentId);
    createdVideoSegmentId = clipResult.segmentId;
    assert.equal(clipResult.startTimeSeconds, 0);
    assert.ok(clipResult.durationSeconds >= 2.9);

    const details = await DraftManager.getProject('UnitTest_Project');
    assert.equal(details.draftContent.materials.videos.length, 1);
    assert.equal(details.draftContent.tracks[0].segments.length, 1);
  });

  await t.test('DraftManager adds audio clip', async () => {
    const audioResult = await DraftManager.addAudioClip({
      projectNameOrId: 'UnitTest_Project',
      filePath: testAudioPath,
      volume: 0.8
    });

    assert.ok(audioResult.segmentId);
    assert.equal(audioResult.startTimeSeconds, 0);

    const details = await DraftManager.getProject('UnitTest_Project');
    assert.equal(details.draftContent.materials.audios.length, 1);
    const audioTrack = details.draftContent.tracks.find(t => t.type === 'audio');
    assert.ok(audioTrack);
    assert.equal(audioTrack.segments.length, 1);
    assert.equal(audioTrack.segments[0].volume, 0.8);
  });

  await t.test('DraftManager sets clip transform', async () => {
    assert.ok(createdVideoSegmentId);
    const transformResult = await DraftManager.setClipTransform('UnitTest_Project', createdVideoSegmentId, {
      scale: 1.25,
      rotation: 15,
      x: 0.1,
      y: -0.2,
      alpha: 0.95
    });

    assert.equal(transformResult.segmentId, createdVideoSegmentId);

    const details = await DraftManager.getProject('UnitTest_Project');
    const seg = details.draftContent.tracks[0].segments.find(s => s.id === createdVideoSegmentId);
    assert.ok(seg && seg.clip);
    assert.equal(seg.clip.scale.x, 1.25);
    assert.equal(seg.clip.rotation, 15);
    assert.equal(seg.clip.transform.x, 0.1);
    assert.equal(seg.clip.transform.y, -0.2);
    assert.equal(seg.clip.alpha, 0.95);
  });

  await t.test('DraftManager trims existing clip', async () => {
    assert.ok(createdVideoSegmentId);
    const trimResult = await DraftManager.trimClip('UnitTest_Project', createdVideoSegmentId, 0.5, 2.0);
    assert.equal(trimResult.newStart, 0.5);
    assert.equal(trimResult.newDuration, 2.0);
  });

  await t.test('DraftManager adds transition to clip', async () => {
    assert.ok(createdVideoSegmentId);
    const transResult = await DraftManager.addTransition({
      projectNameOrId: 'UnitTest_Project',
      segmentId: createdVideoSegmentId,
      transitionName: 'Fade to Black',
      durationSeconds: 0.5
    });

    assert.equal(transResult.name, 'Fade to Black');
    const details = await DraftManager.getProject('UnitTest_Project');
    assert.ok(details.draftContent.materials.transitions && details.draftContent.materials.transitions.length > 0);
  });

  await t.test('DraftManager adds keyframe to clip', async () => {
    assert.ok(createdVideoSegmentId);
    const kfResult = await DraftManager.addKeyframe({
      projectNameOrId: 'UnitTest_Project',
      segmentId: createdVideoSegmentId,
      property: 'scale',
      timeOffsetSeconds: 1.0,
      value: 1.5
    });

    assert.ok(kfResult.keyframeId);
  });

  await t.test('DraftManager adds sticker to project', async () => {
    const stickerResult = await DraftManager.addSticker({
      projectNameOrId: 'UnitTest_Project',
      stickerName: 'FlameEmoji',
      durationSeconds: 2.0
    });

    assert.ok(stickerResult.segmentId);
    const details = await DraftManager.getProject('UnitTest_Project');
    assert.ok(details.draftContent.tracks.some(t => t.type === 'sticker'));
  });

  await t.test('DraftManager renders fast proxy preview via ffmpeg', async () => {
    const previewResult = await DraftManager.generatePreview({
      projectNameOrId: 'UnitTest_Project',
      width: 360,
      height: 640
    });

    assert.ok(previewResult.outputPath);
    assert.ok(previewResult.durationSeconds > 0);
  });


  await t.test('DraftManager adds text overlays to a project', async () => {
    const textResult = await DraftManager.addText({
      projectNameOrId: 'UnitTest_Project',
      text: 'Breaking News',
      startTimeSeconds: 0,
      durationSeconds: 4.5,
      fontSize: 16,
      textColor: '#ffff00ff'
    });

    assert.ok(textResult.segmentId);
    assert.equal(textResult.startTimeSeconds, 0);
    assert.equal(textResult.durationSeconds, 4.5);

    const details = await DraftManager.getProject('UnitTest_Project');
    assert.equal(details.draftContent.materials.texts.length, 1);
  });

  await t.test('DraftManager adds synchronized subtitles from SRT', async () => {
    const srt = `
1
00:00:00,000 --> 00:00:02,000
First subtitle line

2
00:00:02,500 --> 00:00:05,000
Second subtitle line
    `.trim();

    const subResult = await DraftManager.addSubtitles({
      projectNameOrId: 'UnitTest_Project',
      srtContent: srt,
      fontSize: 11
    });

    assert.equal(subResult.addedCount, 2);
    const details = await DraftManager.getProject('UnitTest_Project');
    assert.equal(details.draftContent.materials.texts.length, 3);
  });

  await t.test('DraftManager splits an existing clip accurately', async () => {
    const detailsBefore = await DraftManager.getProject('UnitTest_Project');
    const videoTrack = detailsBefore.draftContent.tracks.find(tr => tr.type === 'video')!;
    const segToSplit = videoTrack.segments[0];

    const splitResult = await DraftManager.splitClip({
      projectNameOrId: 'UnitTest_Project',
      segmentId: segToSplit.id,
      splitTimeSeconds: 1.5
    });

    assert.ok(splitResult.firstSegmentId);
    assert.ok(splitResult.secondSegmentId);
    assert.equal(splitResult.splitTimeSeconds, 1.5);

    const detailsAfter = await DraftManager.getProject('UnitTest_Project');
    const videoTrackAfter = detailsAfter.draftContent.tracks.find(tr => tr.type === 'video')!;
    assert.equal(videoTrackAfter.segments.length, 2);
    assert.equal(videoTrackAfter.segments[0].target_timerange.duration, 1_000_000);
    assert.equal(videoTrackAfter.segments[1].target_timerange.start, 1_500_000);
  });

  await t.test('DraftManager sets clip speed and preserves pitch', async () => {
    const details = await DraftManager.getProject('UnitTest_Project');
    const videoTrack = details.draftContent.tracks.find(tr => tr.type === 'video')!;
    const seg = videoTrack.segments[0];

    const speedResult = await DraftManager.setClipSpeed({
      projectNameOrId: 'UnitTest_Project',
      segmentId: seg.id,
      speed: 2.0,
      preservePitch: true
    });

    assert.equal(speedResult.speed, 2.0);
    const detailsAfter = await DraftManager.getProject('UnitTest_Project');
    const updatedSeg = detailsAfter.draftContent.tracks.find(tr => tr.type === 'video')!.segments[0];
    assert.equal(updatedSeg.speed, 2.0);
    assert.equal(updatedSeg.is_tone_modify, true);
    assert.ok(detailsAfter.draftContent.materials.speeds && detailsAfter.draftContent.materials.speeds.length > 0);
  });

  await t.test('DraftManager adds audio fade-in and fade-out', async () => {
    const details = await DraftManager.getProject('UnitTest_Project');
    const audioTrack = details.draftContent.tracks.find(tr => tr.type === 'audio')!;
    const seg = audioTrack.segments[0];

    const fadeResult = await DraftManager.addAudioFade({
      projectNameOrId: 'UnitTest_Project',
      segmentId: seg.id,
      fadeInSeconds: 1.0,
      fadeOutSeconds: 1.5
    });

    assert.ok(fadeResult.fadeId);
    assert.equal(fadeResult.fadeInSeconds, 1.0);
    assert.equal(fadeResult.fadeOutSeconds, 1.5);

    const detailsAfter = await DraftManager.getProject('UnitTest_Project');
    assert.ok(detailsAfter.draftContent.materials.audio_fades && detailsAfter.draftContent.materials.audio_fades.length > 0);
  });

  await t.test('DraftManager adds viral caption with Aeovisuals styling', async () => {
    const captionResult = await DraftManager.addViralCaption({
      projectNameOrId: 'UnitTest_Project',
      text: 'I MADE 10 MILLION FROM SCRATCH',
      powerWords: ['10 MILLION', 'SCRATCH'],
      fontFamily: 'Montserrat',
      accentColor: '#FF1E27',
      enableHoverPop: true,
      startTimeSeconds: 0,
      durationSeconds: 3.0
    });

    assert.ok(captionResult.segmentId);
    assert.ok(captionResult.materialId);

    const details = await DraftManager.getProject('UnitTest_Project');
    const textMat = details.draftContent.materials.texts.find(t => t.id === captionResult.materialId)!;
    assert.equal(textMat.letter_spacing, -1.0);
    assert.equal(textMat.has_shadow, true);
    assert.equal(textMat.shadow_alpha, 0.26);
    assert.equal(textMat.shadow_smoothing, 0.26);
    assert.equal(textMat.font_title, 'Montserrat');
  });

  await t.test('DraftManager creates video bridge draft', async () => {
    const bridgeResult = await DraftManager.createVideoBridge({
      projectName: 'Bridge_Test_Project',
      videoPlatePath: testVideoPath,
      audioTracks: [{ filePath: testAudioPath, volume: 0.8, trackIndex: 0 }],
      ratio: '9:16',
      fps: 60
    });

    assert.equal(bridgeResult.projectName, 'Bridge_Test_Project');
    assert.ok(bridgeResult.videoSegmentId);

    const details = await DraftManager.getProject('Bridge_Test_Project');
    assert.equal(details.draftContent.canvas_config.ratio, '9:16');
    assert.equal(details.draftContent.fps, 60);
    assert.equal(details.draftContent.tracks.filter(t => t.type === 'video').length, 1);
    assert.equal(details.draftContent.tracks.filter(t => t.type === 'audio').length, 1);
  });

  await t.test('DraftManager adds transient sound effect', async () => {
    const sfxResult = await DraftManager.addSoundEffect({
      projectNameOrId: 'Bridge_Test_Project',
      sfxFilePath: testAudioPath,
      timestampSeconds: 1.0,
      volume: 0.6
    });

    assert.ok(sfxResult.segmentId);
    assert.equal(sfxResult.timestampSeconds, 1.0);

    // Clean up bridge test project so subsequent store count assertions match
    await DraftManager.deleteProject('Bridge_Test_Project', true);
  });

  await t.test('DraftManager duplicates a project', async () => {
    const cloned = await DraftManager.duplicateProject('UnitTest_Project', 'UnitTest_Project_Clone');
    assert.equal(cloned.name, 'UnitTest_Project_Clone');

    const rootMeta = await CapCutPathResolver.readRootMeta();
    assert.equal(rootMeta.all_draft_store.length, 2);
  });

  await t.test('DraftManager deletes a project safely', async () => {
    const delResult = await DraftManager.deleteProject('UnitTest_Project_Clone', true);
    assert.equal(delResult.success, true);

    const rootMeta = await CapCutPathResolver.readRootMeta();
    assert.equal(rootMeta.all_draft_store.length, 1);
    assert.equal(rootMeta.all_draft_store[0].draft_name, 'UnitTest_Project');
  });

  // Cleanup temporary test directory
  await fs.rm(tempDir, { recursive: true, force: true });
});
