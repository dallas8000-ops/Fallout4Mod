function saveLoadOrder() {
    fetch('/save_loadorder', {method: 'POST'})
        .then(r => r.json())
        .then(data => {
            alert('Load order saved to MO2!');
        });
}
