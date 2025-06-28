from datetime import datetime
from sqlalchemy import Column, String, Integer, ForeignKey, TIMESTAMP, Boolean, BigInteger, Text
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

# НОВАЯ МОДЕЛЬ ДЛЯ ЗАРЕГИСТРИРОВАННЫХ ПОЛЬЗОВАТЕЛЕЙ
class BotUser(Base):
    __tablename__ = 'bot_user'

    user_tg_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    registration_date = Column(TIMESTAMP, default=datetime.now)

    # Связь с голосами пользователя
    votes = relationship("Vote", back_populates="user", cascade="all, delete-orphan")

    @property
    def full_name(self):
        """Возвращает полное имя пользователя, если оно есть, иначе username."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.username or str(self.user_tg_id)

class Poll(Base):
    __tablename__ = 'poll'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.now)
    status = Column(Boolean, default=True)

    options = relationship("PollOption", back_populates="poll", cascade="all, delete-orphan")
    # Теперь participants - это голоса, а не пользователи
    participants = relationship("Vote", back_populates="poll", cascade="all, delete-orphan")
    telegram_map = relationship("TelegramPoll", back_populates="poll", cascade="all, delete-orphan")


class PollOption(Base):
    __tablename__ = 'poll_option'

    id = Column(Integer, primary_key=True, index=True)
    poll_id = Column(Integer, ForeignKey('poll.id', ondelete="CASCADE"), nullable=False)
    option_text = Column(Text, nullable=False)
    votes_count = Column(Integer, default=0)

    poll = relationship("Poll", back_populates="options")
    # voters - это голоса
    voters = relationship("Vote", back_populates="option", cascade="all, delete-orphan")


# МОДЕЛЬ User ПЕРЕИМЕНОВАНА В Vote И ПЕРЕРАБОТАНА
class Vote(Base):
    __tablename__ = 'vote'

    id = Column(Integer, primary_key=True, index=True)
    poll_id = Column(Integer, ForeignKey('poll.id', ondelete="CASCADE"), nullable=False)
    # Внешний ключ к ID пользователя из Telegram
    user_tg_id = Column(BigInteger, ForeignKey('bot_user.user_tg_id', ondelete="CASCADE"), nullable=False, index=True)
    option_id = Column(Integer, ForeignKey('poll_option.id', ondelete="CASCADE"), nullable=False)

    # Связи для удобного доступа к данным
    poll = relationship("Poll", back_populates="participants")
    option = relationship("PollOption", back_populates="voters")
    user = relationship("BotUser", back_populates="votes")


class TelegramPoll(Base):
    __tablename__ = 'telegram_poll'

    telegram_poll_id = Column(String, primary_key=True)
    poll_id = Column(Integer, ForeignKey('poll.id', ondelete="CASCADE"), nullable=False)

    poll = relationship("Poll", back_populates="telegram_map")