import React from 'react';
import renderer, { act } from 'react-test-renderer';
import App from '../App';

describe('production startup render', () => {
  it('renders App without throwing', async () => {
    await act(async () => {
      renderer.create(<App />);
    });
  });
});
