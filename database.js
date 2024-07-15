const { Sequelize, DataTypes } = require('sequelize');
const sequelize = new Sequelize({
    dialect: 'sqlite',
    storage: './database.sqlite' // Путь к файлу базы данных
});

const LightState = sequelize.define('LightState', {
    chatId: {
        type: DataTypes.STRING,
        primaryKey: true,
        allowNull: false
    },
    state: {
        type: DataTypes.STRING,
        allowNull: false
    },
    startTime: {
        type: DataTypes.DATE,
        allowNull: false
    },
    duration: {
        type: DataTypes.STRING,
        allowNull: true
    }
});

sequelize.sync()
    .then(() => console.log('База данных синхронизирована'))
    .catch(err => console.error('Ошибка при синхронизации базы данных:', err));

module.exports = { LightState };
