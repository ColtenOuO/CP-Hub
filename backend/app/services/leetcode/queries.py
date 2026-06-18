# backend/app/services/leetcode/queries.py

# Get problem list with specific difficulty and tags
LEETCODE_PROBLEM_LIST_QUERY = """
query problemsetQuestionListV2(
  $categorySlug: String,
  $limit: Int,
  $skip: Int,
  $filters: QuestionFilterInput
) {
  problemsetQuestionListV2(
    categorySlug: $categorySlug,
    limit: $limit,
    skip: $skip,
    filters: $filters
  ) {
    questions {
      questionFrontendId
      title
      titleSlug
      difficulty
      paidOnly
    }
  }
}
"""

# Check whether a LeetCode account with the given username exists
LEETCODE_USER_PROFILE_QUERY = """
query getUserProfile($username: String!) {
  matchedUser(username: $username) {
    username
  }
}
"""

# Get the number of problems a user has solved, grouped by difficulty
LEETCODE_USER_SOLVED_STATS_QUERY = """
query getUserProfile($username: String!) {
  matchedUser(username: $username) {
    username
    submitStatsGlobal {
      acSubmissionNum {
        difficulty
        count
      }
    }
  }
}
"""

# Get recent accepted submissions for a user (up to 20)
LEETCODE_RECENT_AC_SUBMISSIONS_QUERY = """
query getRecentAcSubmissions($username: String!, $limit: Int!) {
  recentAcSubmissionList(username: $username, limit: $limit) {
    titleSlug
    timestamp
  }
}
"""
