document.addEventListener('DOMContentLoaded', function () {
    // 초기 데이터 로드
    loadGardeners();

    // 정원사들 목록 로드
    function loadGardeners() {
        fetch('/api/users')
            .then(response => response.json())
            .then(data => {
                const gardenersList = document.getElementById('gardeners-list');
                gardenersList.innerHTML = '';

                data.forEach(user => {
                    const userDiv = document.createElement('div');
                    userDiv.className = 'gardener';
                    userDiv.innerHTML = `
                <img src="${user.github_profile_url}" alt="${user.github_id}" title="${user.github_id}">
                <span>${user.github_id}</span>
            `;
                    gardenersList.appendChild(userDiv);
                });
            });
    }

});