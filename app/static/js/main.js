document.addEventListener('DOMContentLoaded', function () {
    // 초기 데이터 로드
    loadGardeners();
    checkAuthStatus();

    // 로그인 버튼 이벤트 리스너
    document.getElementById('login-btn').addEventListener('click', function() {
        window.location.href = '/api/auth/login';
    });

    // 로그아웃 버튼 이벤트 리스너
    document.getElementById('logout-btn').addEventListener('click', function() {
        window.location.href = '/api/auth/logout';
    });

    // 새로고침 버튼 이벤트 리스너
    document.getElementById('refresh-btn').addEventListener('click', function() {
        loadGardeners();
        showNotification('출석부가 갱신되었습니다.');
    });

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

    // 인증 상태 확인
    function checkAuthStatus() {
        fetch('/api/auth/me')
            .then(response => {
                if (!response.ok) {
                    throw new Error('인증 실패');
                }
                return response.json();
            })
            .then(userData => {
                // 로그인 성공 상태
                document.getElementById('login-btn').classList.add('hidden');
                const userProfile = document.getElementById('user-profile');
                userProfile.classList.remove('hidden');
                
                // 사용자 정보 표시
                document.getElementById('user-avatar').src = userData.github_profile_url;
                document.getElementById('user-name').textContent = userData.github_id;
            })
            .catch(error => {
                // 로그인 안된 상태
                document.getElementById('login-btn').classList.remove('hidden');
                document.getElementById('user-profile').classList.add('hidden');
            });
    }

    // 알림 메시지 표시
    function showNotification(message, isError = false) {
        const notification = document.createElement('div');
        notification.className = isError ? 'notification error' : 'notification';
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        // 3초 후 알림 제거
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
});