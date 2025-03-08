document.addEventListener('DOMContentLoaded', function() {
    // 초기 데이터 로드
    loadGardeners();

    // 정원사들 목록 로드
    function loadGardeners() {
        let data = [
            {
                "github_id": "user1",
                "name": "사용자1",
                "github_profile_url": "https://avatars.githubusercontent.com/u/1"
            },
            {
                "github_id": "user2",
                "name": "사용자2",
                "github_profile_url": "https://avatars.githubusercontent.com/u/2"
            },
            {
                "github_id": "user3",
                "name": "사용자3",
                "github_profile_url": "https://avatars.githubusercontent.com/u/3"
            },
            {
                "github_id": "user4",
                "name": "사용자4",
                "github_profile_url": "https://avatars.githubusercontent.com/u/4"
            },
            {
                "github_id": "user5",
                "name": "사용자5",
                "github_profile_url": "https://avatars.githubusercontent.com/u/5"
            }
        ];

        const gardenersList = document.getElementById('gardeners-list');
        gardenersList.innerHTML = '';

        data.forEach(user => {
            const userDiv = document.createElement('div');
            userDiv.className = 'gardener';
            userDiv.innerHTML = `
                <img src="${user.github_profile_url}" alt="${user.github_id}" title="${user.name}">
                <span>${user.github_id}</span>
            `;
            gardenersList.appendChild(userDiv);
        });
    }

});