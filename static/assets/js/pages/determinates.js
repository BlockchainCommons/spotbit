
    //ON FAQ and ABOUT
    (function () {
        const determinates = document.querySelectorAll('.mdc-linear-progress');
        for (let i = 0, determinate; determinate = determinates[i]; i++) {
          const linearProgress = mdc.linearProgress.MDCLinearProgress.attachTo(determinate);
          linearProgress.progress = 0.5;
          if (determinate.dataset.buffer) {
            linearProgress.buffer = 0.75;
          }
        }
  
        // // //TODO:MISSING HTML MARKUP
        // // Tabs example.
        // new mdc.tabBar.MDCTabBar(document.querySelector('.mdc-tab-bar'));
  
        // // Checkbox
        // document.getElementById('basic-indeterminate-checkbox').indeterminate = true;
  
        // // Textfields
        // const tfRoot = document.querySelectorAll('.mdc-text-field');
        // for (let i = 0; i < tfRoot.length; i++) {
        //   new mdc.textField.MDCTextField(tfRoot[i]);
        // }
  
        // // Select
        // new mdc.select.MDCSelect(document.querySelector('.mdc-select'));
  
        // // Slider
        // const MDCSlider = mdc.slider.MDCSlider;
        // const elements = document.querySelectorAll('.mdc-slider');
        // for (let i = 0; i < elements.length; i++) {
        //   new MDCSlider(elements[i]);
        // }
      })();