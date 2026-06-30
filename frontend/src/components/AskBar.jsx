import Typewriter from 'typewriter-effect';

const CoffeeAskBar = () => {
    return (
        <div className="typewriter-text">
            <Typewriter
                options={{
                    strings: [
                        '歡迎來到啡你莫屬',
                        '跟 AI 聊天來尋找咖啡廳',
                        '讓 AI 為你規劃下一場味覺旅行',
                    ],
                    autoStart: true,
                    loop: true,
                    delay: 75,
                    deleteSpeed: 50,
                    pauseFor: 2000,
                }}
            />
        </div>
    );
};

export default CoffeeAskBar;