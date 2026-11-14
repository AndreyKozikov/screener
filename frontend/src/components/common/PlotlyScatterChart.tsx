import Plotly from 'plotly.js/lib/core';
import * as scatter from 'plotly.js/lib/scatter';
import createPlotlyComponent from 'react-plotly.js/factory';

Plotly.register([scatter]);

const Plot = createPlotlyComponent(Plotly);

export default Plot;
