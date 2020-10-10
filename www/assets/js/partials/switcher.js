(function() {
  "use strict";

  const cryptoRtlSwitch = document.querySelector('.crypto-rtl-switch-selector');
  const cryptoThemeSwitch = document.querySelector('.crypto-theme-switch-selector');
  const cryptoRtlSwitchInstance = new mdc.switchControl.MDCSwitch(cryptoRtlSwitch);
  const cryptoThemeSwitchInstance = new mdc.switchControl.MDCSwitch(cryptoThemeSwitch);
  const cryptoThemeSwitchContainer = document.querySelector('.crypto-menu-switches');
  const cryptoThemeSwitchHandle = document.querySelector('.crypto-menu-switches--handle');

  cryptoThemeSwitchHandle.addEventListener('click', function(){
    cryptoThemeSwitchContainer.classList.toggle('shown');
  });

  // Check if theme has been stored in session.
  const themeID = sessionStorage.getItem('crypto-html-theme');
  if (themeID) {
    switchTheme(themeID);
    if (themeID === 'light-purple-red') {
      document.querySelector('.crypto-theme-switch-selector').classList.add('mdc-switch--checked');
      cryptoThemeSwitchInstance.checked = true;
    }
  }

  // Check if RTL has been stored in session.
  const isRtl = sessionStorage.getItem('crypto-html-rtl');
  if (isRtl) { // Checks if a cookie is set for RTL. It will be a string 'true' or 'false'.
    if (isRtl === 'true') {
      document.documentElement.dir = 'rtl';
      document.querySelector('.crypto-rtl-switch-selector').classList.add('mdc-switch--checked');
      cryptoRtlSwitchInstance.checked = true;
    } else {
      document.documentElement.dir = 'ltr';
      cryptoRtlSwitchInstance.checked = false;
    }
  }

  // Add listener for the RTL switch.
  const rtlSwitch = document.getElementById('rtl-switch');
  if (rtlSwitch !== null) {
    mdc.iconToggle.MDCIconToggle.attachTo(rtlSwitch);
    rtlSwitch.addEventListener('change', function(evt) {
      document.documentElement.dir = evt.target.checked ? 'rtl' : 'ltr';
      // Store rtl.
      sessionStorage.setItem('crypto-html-rtl', evt.target.checked);
    });
  }

  // Add listener for the theme switch.
  const themeSwitch = document.getElementById('crypto-theme-switch');
  if (themeSwitch !== null) {
    themeSwitch.addEventListener('change', function(evt) {
      // Switch theme
      const themeID = evt.target.checked ? 'light-purple-red' : 'night-gold-orange';
      switchTheme(themeID);
      // Store theme.
      sessionStorage.setItem('crypto-html-theme', themeID);
      // Dispatch event to update the charts
      const body = document.getElementsByTagName('body').item(0);
      const event = new Event('cryptoThemeChanged');
      setTimeout(function() {
        body.dispatchEvent(event);
      }, 500);
    });
  }

  function switchTheme(themeID) {
    const stylesheetLink = document.querySelector('#crypto-stylesheet');
    const currentStylesheetFilename = stylesheetLink.href.substring(stylesheetLink.href.lastIndexOf('/') + 1);
    const newStylesheetURL = stylesheetLink.href.replace(currentStylesheetFilename, themeID + '.css');
    const head = document.getElementsByTagName('head').item(0);
    const newlink = document.createElement('link');

    // Create new link.
    newlink.setAttribute('rel', 'stylesheet');
    newlink.setAttribute('type', 'text/css');
    newlink.setAttribute('href', newStylesheetURL);
    // Add new link to head.
    head.appendChild(newlink, stylesheetLink);
    // Add load listener to remove old CSS link.
    newlink.addEventListener('load', function() {
      // Remove old CSS link.
      head.removeChild(stylesheetLink);
      // Set new link to use id.
      newlink.setAttribute('id', 'crypto-stylesheet');
    });
  }
})();
