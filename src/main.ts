// Composition root. Step 1 wires only the chart container; the data source,
// model and controls are added in step 3.
import './style.css';
import { echarts } from './chart/echarts-setup.ts';

const container = document.querySelector<HTMLDivElement>('#chart');
if (!container) throw new Error('#chart container is missing from index.html');

const chart = echarts.init(container, undefined, { renderer: 'canvas' });
window.addEventListener('resize', () => chart.resize());

const status = document.querySelector<HTMLParagraphElement>('#status');
if (status) status.textContent = 'Scaffold only: data layer arrives in step 3.';
